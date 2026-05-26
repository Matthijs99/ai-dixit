from dataclasses import dataclass, field

from dixit_ai.elo import ensure_model_entries, expected_score, update_ratings


@dataclass
class _FakePlayer:
    model_id: str
    display_name: str
    org: str
    previous_ids: list[str] = field(default_factory=list)

def test_expected_score_equal_ratings():
    assert abs(expected_score(1500, 1500) - 0.5) < 1e-9

def test_expected_score_higher_rated_favored():
    # A rated 100 above B: E_A should be > 0.5.
    e_a = expected_score(1600, 1500)
    assert 0.5 < e_a < 1.0

def test_pairwise_update_winner_gains():
    # placements: A=1st, B=2nd
    ratings = {"A": 1500, "B": 1500}
    placements = ["A", "B"]
    new = update_ratings(ratings, placements)
    assert new["A"] > 1500
    assert new["B"] < 1500
    # K=32 with equal ratings: winner +16, loser -16.
    assert round(new["A"] - 1500) == 16
    assert round(1500 - new["B"]) == 16

def test_total_delta_is_zero():
    ratings = {"A": 1500, "B": 1450, "C": 1550, "D": 1400, "E": 1600}
    placements = ["C", "A", "E", "B", "D"]
    new = update_ratings(ratings, placements)
    delta_sum = sum(new[m] - ratings[m] for m in ratings)
    assert abs(delta_sum) < 1e-6, f"delta sum drift: {delta_sum}"

def test_five_player_sweep_top_gains_about_50():
    ratings = {f"p{i}": 1500 for i in range(5)}
    placements = [f"p{i}" for i in range(5)]
    new = update_ratings(ratings, placements)
    # Top finisher beats 4 equal-rated opponents → 4 * K * (1 - 0.5) = 64.
    # Bottom loses to 4: -64.
    assert round(new["p0"] - 1500) == 64
    assert round(1500 - new["p4"]) == 64

def test_ties_in_score_treated_as_draws():
    # Two players tied at the same final score should get the same Elo delta.
    ratings = {"A": 1500, "B": 1500, "C": 1500, "D": 1500, "E": 1500}
    scores = {"A": 32, "B": 29, "C": 29, "D": 21, "E": 19}
    # Placement order between B and C is arbitrary; result should be symmetric.
    placements = ["A", "B", "C", "D", "E"]
    new = update_ratings(ratings, placements, scores=scores)
    # B and C should end with identical ratings — the tie removes any bias.
    assert abs(new["B"] - new["C"]) < 1e-9
    # Sanity: top beats both ties; ties beat the bottom two.
    assert new["A"] > new["B"] > new["D"] > new["E"]
    # With equal pre-game ratings, the B-vs-C draw contributes zero, so
    # B and C each only differ from 1500 by their other three pair results:
    # lose to A (-16), beat D (+16), beat E (+16) → net +16.
    assert round(new["B"] - 1500) == 16
    assert round(new["C"] - 1500) == 16


def test_symmetry_same_rating_same_placement():
    # Two players with identical ratings and identical placement (a tie) get identical updates.
    # Our model has no ties — the caller breaks them — so we instead test that
    # adjacent placements with identical ratings yield symmetric deltas.
    ratings = {"A": 1500, "B": 1500, "C": 1500}
    new = update_ratings(ratings, ["A", "B", "C"])
    # A finished above B and C; B above C.
    # The middle player B has 1 win (vs C) and 1 loss (vs A): net 0.
    assert round(new["B"] - 1500) == 0


def test_ensure_entries_inits_fresh_for_new_model():
    elo: dict = {"models": {}}
    p = _FakePlayer(model_id="new", display_name="New", org="Lab")
    ensure_model_entries(elo, [p])
    assert elo["models"]["new"] == {
        "display_name": "New",
        "org": "Lab",
        "rating": 1500.0,
        "games": 0,
        "wins": 0,
    }


def test_ensure_entries_carries_over_via_previous_ids():
    elo: dict = {
        "models": {
            "old": {
                "display_name": "Old",
                "org": "Lab",
                "rating": 1623.5,
                "games": 7,
                "wins": 2,
            }
        }
    }
    p = _FakePlayer(
        model_id="new", display_name="New", org="Lab", previous_ids=["old"]
    )
    ensure_model_entries(elo, [p])
    # New entry inherits rating/games/wins from "old".
    assert elo["models"]["new"]["rating"] == 1623.5
    assert elo["models"]["new"]["games"] == 7
    assert elo["models"]["new"]["wins"] == 2
    # New entry uses the new player's display_name, not the old one's.
    assert elo["models"]["new"]["display_name"] == "New"
    # Old entry is preserved as a retired record, now flagged so the
    # leaderboard can hide it while history still resolves.
    assert "old" in elo["models"]
    assert elo["models"]["old"]["rating"] == 1623.5
    assert elo["models"]["old"].get("retired") is True
    assert "retired" not in elo["models"]["new"]


def test_ensure_entries_flags_models_absent_from_roster():
    # A model present in elo.json but not in the active roster is retired;
    # a model still in the roster has any stale retired flag cleared.
    elo: dict = {
        "models": {
            "dropped": {
                "display_name": "Dropped",
                "org": "Lab",
                "rating": 1500.0,
                "games": 4,
                "wins": 1,
            },
            "kept": {
                "display_name": "Kept",
                "org": "Lab",
                "rating": 1510.0,
                "games": 4,
                "wins": 1,
                "retired": True,
            },
        }
    }
    p = _FakePlayer(model_id="kept", display_name="Kept", org="Lab")
    ensure_model_entries(elo, [p])
    assert elo["models"]["dropped"].get("retired") is True
    assert "retired" not in elo["models"]["kept"]


def test_ensure_entries_skips_existing():
    elo: dict = {
        "models": {
            "x": {
                "display_name": "X",
                "org": "Lab",
                "rating": 1700.0,
                "games": 3,
                "wins": 1,
            }
        }
    }
    p = _FakePlayer(model_id="x", display_name="Renamed", org="Lab")
    ensure_model_entries(elo, [p])
    # Existing entry is left untouched — display_name not overwritten.
    assert elo["models"]["x"]["display_name"] == "X"
    assert elo["models"]["x"]["rating"] == 1700.0
