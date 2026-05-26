from dataclasses import dataclass, field

from dixit_ai.elo import (
    INITIAL_RATING,
    INITIAL_RD,
    INITIAL_VOL,
    ensure_model_entries,
    glicko2_update,
    update_ratings,
)


@dataclass
class _FakePlayer:
    model_id: str
    display_name: str
    org: str
    previous_ids: list[str] = field(default_factory=list)


# ----- Core Glicko-2 step -----

def test_glickman_paper_worked_example():
    # The canonical example from Glickman's Glicko-2 paper (glicko2.pdf):
    # a player rated 1500/RD 200/vol 0.06 plays three opponents and should
    # end at rating 1464.06, RD 151.52, vol 0.05999.
    matches = [
        (1400, 30, 1.0),   # win
        (1550, 100, 0.0),  # loss
        (1700, 300, 0.0),  # loss
    ]
    r, rd, vol = glicko2_update(1500, 200, 0.06, matches, tau=0.5)
    assert abs(r - 1464.06) < 0.05
    assert abs(rd - 151.52) < 0.05
    assert abs(vol - 0.05999) < 1e-4


def test_no_matches_only_inflates_rd():
    # A rating period with no games leaves rating/vol unchanged and raises RD.
    r, rd, vol = glicko2_update(1500, 200, 0.06, [])
    assert r == 1500
    assert rd > 200
    assert vol == 0.06


# ----- One-game round robin (update_ratings) -----

def _equal(*ids):
    return {i: (INITIAL_RATING, INITIAL_RD, INITIAL_VOL) for i in ids}


def test_winner_gains_loser_loses():
    states = _equal("A", "B")
    new = update_ratings(states, {"A": 10, "B": 5})
    assert new["A"][0] > INITIAL_RATING
    assert new["B"][0] < INITIAL_RATING
    # Symmetric: equal start, opposite results.
    assert abs((new["A"][0] - INITIAL_RATING) + (new["B"][0] - INITIAL_RATING)) < 1e-6


def test_playing_shrinks_rd():
    states = _equal("A", "B", "C", "D", "E")
    new = update_ratings(states, {"A": 30, "B": 25, "C": 20, "D": 15, "E": 10})
    for m in states:
        assert new[m][1] < INITIAL_RD  # RD drops once a model has evidence


def test_higher_score_ranks_higher():
    states = _equal("A", "B", "C", "D", "E")
    new = update_ratings(states, {"A": 30, "B": 25, "C": 20, "D": 15, "E": 10})
    order = sorted(states, key=lambda m: -new[m][0])
    assert order == ["A", "B", "C", "D", "E"]


def test_tied_scores_are_symmetric():
    states = _equal("A", "B", "C", "D", "E")
    # B and C tie on points; with equal pre-game ratings they must end identical.
    new = update_ratings(states, {"A": 32, "B": 29, "C": 29, "D": 21, "E": 19})
    assert abs(new["B"][0] - new["C"][0]) < 1e-9
    assert abs(new["B"][1] - new["C"][1]) < 1e-9
    assert new["A"][0] > new["B"][0] > new["D"][0] > new["E"][0]


def test_update_does_not_mutate_input():
    states = _equal("A", "B")
    snapshot = dict(states)
    update_ratings(states, {"A": 10, "B": 5})
    assert states == snapshot


# ----- Roster bookkeeping -----

def test_ensure_entries_inits_fresh_with_glicko_fields():
    elo: dict = {"models": {}}
    p = _FakePlayer(model_id="new", display_name="New", org="Lab")
    ensure_model_entries(elo, [p])
    assert elo["models"]["new"] == {
        "display_name": "New",
        "org": "Lab",
        "rating": INITIAL_RATING,
        "rd": INITIAL_RD,
        "vol": INITIAL_VOL,
        "games": 0,
        "wins": 0,
    }


def test_ensure_entries_carries_over_rating_rd_vol():
    elo: dict = {
        "models": {
            "old": {
                "display_name": "Old",
                "org": "Lab",
                "rating": 1623.5,
                "rd": 142.0,
                "vol": 0.055,
                "games": 7,
                "wins": 2,
            }
        }
    }
    p = _FakePlayer(model_id="new", display_name="New", org="Lab", previous_ids=["old"])
    ensure_model_entries(elo, [p])
    new = elo["models"]["new"]
    assert (new["rating"], new["rd"], new["vol"]) == (1623.5, 142.0, 0.055)
    assert new["games"] == 7 and new["wins"] == 2
    assert new["display_name"] == "New"
    # Old entry preserved and flagged retired.
    assert elo["models"]["old"].get("retired") is True
    assert "retired" not in new


def test_ensure_entries_flags_models_absent_from_roster():
    elo: dict = {
        "models": {
            "dropped": {"display_name": "D", "org": "L", "rating": 1500.0,
                        "rd": 350.0, "vol": 0.06, "games": 4, "wins": 1},
            "kept": {"display_name": "K", "org": "L", "rating": 1510.0,
                     "rd": 200.0, "vol": 0.06, "games": 4, "wins": 1, "retired": True},
        }
    }
    p = _FakePlayer(model_id="kept", display_name="K", org="L")
    ensure_model_entries(elo, [p])
    assert elo["models"]["dropped"].get("retired") is True
    assert "retired" not in elo["models"]["kept"]


def test_ensure_entries_skips_existing():
    elo: dict = {
        "models": {
            "x": {"display_name": "X", "org": "L", "rating": 1700.0,
                  "rd": 120.0, "vol": 0.06, "games": 3, "wins": 1},
        }
    }
    p = _FakePlayer(model_id="x", display_name="Renamed", org="L")
    ensure_model_entries(elo, [p])
    assert elo["models"]["x"]["display_name"] == "X"
    assert elo["models"]["x"]["rating"] == 1700.0
