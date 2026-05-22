from dixit_ai.elo import expected_score, update_ratings, K

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

def test_symmetry_same_rating_same_placement():
    # Two players with identical ratings and identical placement (a tie) get identical updates.
    # Our model has no ties — the caller breaks them — so we instead test that
    # adjacent placements with identical ratings yield symmetric deltas.
    ratings = {"A": 1500, "B": 1500, "C": 1500}
    new = update_ratings(ratings, ["A", "B", "C"])
    # A finished above B and C; B above C.
    # The middle player B has 1 win (vs C) and 1 loss (vs A): net 0.
    assert round(new["B"] - 1500) == 0
