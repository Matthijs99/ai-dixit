from dataclasses import dataclass

from dixit_ai.stats import ensure_model_entries, record_game


@dataclass
class _FakePlayer:
    model_id: str
    display_name: str
    org: str


# ----- Recording results -----

def test_record_game_accumulates_points_games_wins():
    models = {
        "A": {"display_name": "A", "org": "L", "games": 0, "wins": 0, "points": 0},
        "B": {"display_name": "B", "org": "L", "games": 0, "wins": 0, "points": 0},
    }
    record_game(models, {"A": 30, "B": 18}, winner="A")
    assert models["A"] == {"display_name": "A", "org": "L", "games": 1, "wins": 1, "points": 30}
    assert models["B"] == {"display_name": "B", "org": "L", "games": 1, "wins": 0, "points": 18}
    # A second game keeps a running total; only the winner's wins increments.
    record_game(models, {"A": 12, "B": 25}, winner="B")
    assert models["A"]["games"] == 2 and models["A"]["points"] == 42 and models["A"]["wins"] == 1
    assert models["B"]["games"] == 2 and models["B"]["points"] == 43 and models["B"]["wins"] == 1


# ----- Roster bookkeeping -----

def test_ensure_entries_inits_fresh():
    stats: dict = {"models": {}}
    p = _FakePlayer(model_id="new", display_name="New", org="Lab")
    ensure_model_entries(stats, [p])
    assert stats["models"]["new"] == {
        "display_name": "New",
        "org": "Lab",
        "games": 0,
        "wins": 0,
        "points": 0,
    }


def test_ensure_entries_flags_models_absent_from_roster():
    stats: dict = {
        "models": {
            "dropped": {"display_name": "D", "org": "L", "games": 4, "wins": 1, "points": 80},
            "kept": {"display_name": "K", "org": "L", "games": 4, "wins": 1,
                     "points": 88, "retired": True},
        }
    }
    p = _FakePlayer(model_id="kept", display_name="K", org="L")
    ensure_model_entries(stats, [p])
    # A model no longer in the roster is retired; one that returns has the flag cleared.
    assert stats["models"]["dropped"].get("retired") is True
    assert "retired" not in stats["models"]["kept"]


def test_ensure_entries_skips_existing():
    stats: dict = {
        "models": {
            "x": {"display_name": "X", "org": "L", "games": 3, "wins": 1, "points": 60},
        }
    }
    p = _FakePlayer(model_id="x", display_name="Renamed", org="L")
    ensure_model_entries(stats, [p])
    # Existing tallies and metadata are left untouched.
    assert stats["models"]["x"]["display_name"] == "X"
    assert stats["models"]["x"]["points"] == 60


# ----- Aliased models (same model under two ids share one line) -----

def test_record_game_folds_aliased_model_into_canonical():
    # claude-opus-4-7-thinking is the same model as claude-opus-4-7, so its
    # game must accumulate onto the canonical entry, not a separate one.
    models = {
        "claude-opus-4-7": {"display_name": "Claude Opus 4.7", "org": "Anthropic",
                            "games": 5, "wins": 1, "points": 131},
    }
    record_game(models, {"claude-opus-4-7-thinking": 30}, winner="claude-opus-4-7-thinking")
    assert "claude-opus-4-7-thinking" not in models
    entry = models["claude-opus-4-7"]
    assert entry["games"] == 6
    assert entry["points"] == 161
    assert entry["wins"] == 2


def test_ensure_entries_keeps_aliased_active_model_under_canonical():
    # The roster lists the thinking id, but it should keep the canonical entry
    # active (clear `retired`) rather than spawn a second row.
    stats: dict = {
        "models": {
            "claude-opus-4-7": {"display_name": "Claude Opus 4.7", "org": "Anthropic",
                                "games": 5, "wins": 1, "points": 131, "retired": True},
        }
    }
    p = _FakePlayer(model_id="claude-opus-4-7-thinking",
                    display_name="Claude Opus 4.7", org="Anthropic")
    ensure_model_entries(stats, [p])
    assert "claude-opus-4-7-thinking" not in stats["models"]
    assert "retired" not in stats["models"]["claude-opus-4-7"]
