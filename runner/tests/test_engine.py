from dixit_ai.engine import score_turn, play_game, GameResult
from dixit_ai.players.random_player import RandomPlayer
from dixit_ai.players.base import MoveError

# Each test specifies:
#   storyteller: model_id
#   storyteller_card: int
#   submissions: {model: card_id} — does NOT need to include storyteller; engine adds it
#   votes: {voter: voted_card_id} — only non-storytellers; missing voter = vote forfeit
#   expected: {model: delta}

def test_partial_correct_votes():
    # Storyteller card = 1. Two voters guess 1, two guess decoys.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 2, "D": 3}
    delta = score_turn("S", 1, submissions, votes)
    # Storyteller gets 3 (some but not all guessed correctly)
    # A, B guessed correctly → 3 each
    # C, D guessed wrong → 0 base
    # Decoy bonuses: card 2 got 1 vote → A gets +1; card 3 got 1 vote → B gets +1.
    assert delta == {"S": 3, "A": 3 + 1, "B": 3 + 1, "C": 0, "D": 0}

def test_all_correct_votes():
    # All 4 non-storytellers vote for the storyteller's card → storyteller gets 0,
    # everyone else gets 2.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 1, "D": 1}
    delta = score_turn("S", 1, submissions, votes)
    assert delta == {"S": 0, "A": 2, "B": 2, "C": 2, "D": 2}

def test_no_correct_votes():
    # None voted for storyteller's card.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    # A→3 (B's card), B→2 (A's card), C→5 (D's card), D→4 (C's card)
    votes = {"A": 3, "B": 2, "C": 5, "D": 4}
    delta = score_turn("S", 1, submissions, votes)
    # Storyteller: 0 (no one guessed → all-or-none applies).
    # Each voter: 2 base (all-or-none).
    # Decoy bonuses: card 2 got 1 vote (B); card 3 got 1 vote (A);
    # card 4 got 1 vote (D); card 5 got 1 vote (C).
    assert delta == {"S": 0, "A": 2 + 1, "B": 2 + 1, "C": 2 + 1, "D": 2 + 1}

def test_decoy_bonus_capped_at_3():
    # Construct a 6-player hypothetical to force a decoy bonus >3.
    # In the real game N=5, but score_turn is general.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5, "E": 6}
    # All 5 voters guess card 2 (A's decoy). Cap kicks in.
    votes = {"A": 1, "B": 2, "C": 2, "D": 2, "E": 2}
    # Wait — A guessed correctly (1), so storyteller is NOT all-or-none.
    # Storyteller gets 3, A gets 3.
    # Decoy bonus for card 2: 4 votes → A gets +3 (capped).
    delta = score_turn("S", 1, submissions, votes)
    assert delta["A"] == 3 + 3
    assert delta["S"] == 3

def test_vote_forfeit_excluded_from_denominator():
    # 4 non-storytellers, but D forfeited their vote.
    # Among the 3 who voted: all 3 voted correctly → all-or-none applies → storyteller 0, others 2.
    # D (forfeit) gets 0 plus any decoy bonus.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 1}  # D missing
    delta = score_turn("S", 1, submissions, votes)
    assert delta == {"S": 0, "A": 2, "B": 2, "C": 2, "D": 0}

def test_pick_forfeit_no_card_no_decoy_bonus():
    # A forfeited their pick: not in submissions, not in votes.
    submissions = {"S": 1, "B": 3, "C": 4, "D": 5}  # A omitted
    votes = {"B": 1, "C": 3, "D": 4}  # A omitted
    delta = score_turn("S", 1, submissions, votes)
    # Among participants (B, C, D): only B voted correctly → partial → storyteller 3, B 3.
    # Decoy bonus: card 3 got 1 vote → B +1; card 4 got 1 vote → C +1.
    # A is NOT in the returned delta (caller handles forfeiters).
    assert "A" not in delta
    assert delta == {"S": 3, "B": 3 + 1, "C": 0 + 1, "D": 0}


def make_random_players(n: int = 5, base_seed: int = 100) -> list[RandomPlayer]:
    return [RandomPlayer(model_id=f"r{i}", seed=base_seed + i) for i in range(n)]


def test_game_terminates_under_turn_cap():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    assert isinstance(result, GameResult)
    assert len(result.turns) <= 50
    assert result.status in {"complete", "turn_limit"}
    assert set(result.final_scores.keys()) == {p.model_id for p in players}


def test_game_winner_has_highest_score():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    winner = result.winner
    assert winner is not None
    assert result.final_scores[winner] == max(result.final_scores.values())


def test_determinism_with_same_seed():
    a = play_game(make_random_players(), rng_seed="x")
    b = play_game(make_random_players(), rng_seed="x")
    assert a.final_scores == b.final_scores
    assert a.status == b.status
    assert [t.turn for t in a.turns] == [t.turn for t in b.turns]


def test_hands_stay_at_size_six():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    # The engine should never have left a player with fewer than 6 cards mid-game,
    # because reshuffling keeps the deck non-empty.
    for snap in result.hand_size_snapshots:
        for size in snap.values():
            assert size == 6, f"hand shrank to {size}"


def test_storyteller_rotates():
    players = make_random_players(3)  # 3 players, easier to verify rotation
    result = play_game(players, rng_seed="test")
    expected_storytellers = [players[i % 3].model_id for i in range(len(result.turns))]
    actual = [t.storyteller for t in result.turns]
    assert actual == expected_storytellers


def test_face_up_order_includes_storyteller_card():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    for t in result.turns:
        if t.face_up_order:
            assert t.storyteller_card in t.face_up_order


class ForfeitingStoryteller:
    model_id = "F"
    display_name = "F"
    org = "test"

    def __init__(self, forfeit_phase: str):
        self.phase = forfeit_phase

    def storytell(self, hand):
        if self.phase == "storytell":
            raise MoveError("nope")
        return hand[0].id, "clue"

    def pick_for_clue(self, hand, clue):
        if self.phase == "pick":
            raise MoveError("nope")
        return hand[0].id

    def vote(self, face_up_cards, clue, own_card_id):
        if self.phase == "vote":
            raise MoveError("nope")
        choices = [c for c in face_up_cards if c.id != own_card_id]
        return choices[0].id


def make_mixed_players(forfeit_phase: str):
    # F always forfeits at the given phase. Others are RandomPlayers.
    return [
        ForfeitingStoryteller(forfeit_phase),
        RandomPlayer(model_id="a", seed=1),
        RandomPlayer(model_id="b", seed=2),
        RandomPlayer(model_id="c", seed=3),
        RandomPlayer(model_id="d", seed=4),
    ]


def test_storyteller_forfeit_skips_turn():
    players = make_mixed_players("storytell")
    result = play_game(players, rng_seed="seed1")
    # Every turn where F was storyteller should have degraded contain
    # "F:storytell:forfeit" and have empty submissions/votes.
    forfeits = [t for t in result.turns if "F:storytell:forfeit" in t.degraded]
    assert forfeits, "expected at least one storyteller forfeit"
    for t in forfeits:
        assert t.submissions == {}
        assert t.votes == {}
        assert t.clue is None
        assert all(d == 0 for d in t.scores_delta.values())


def test_pick_forfeit_removes_from_submissions_and_votes():
    players = make_mixed_players("pick")
    result = play_game(players, rng_seed="seed2")
    # Find any turn where F was NOT storyteller (i.e. F was supposed to pick).
    f_pick_turns = [t for t in result.turns if t.storyteller != "F" and "F:pick:forfeit" in t.degraded]
    assert f_pick_turns
    for t in f_pick_turns:
        assert "F" not in t.submissions
        assert "F" not in t.votes


def test_vote_forfeit_keeps_submission_omits_vote():
    players = make_mixed_players("vote")
    result = play_game(players, rng_seed="seed3")
    f_vote_turns = [t for t in result.turns if t.storyteller != "F" and "F:vote:forfeit" in t.degraded]
    assert f_vote_turns
    for t in f_vote_turns:
        assert "F" in t.submissions
        assert "F" not in t.votes
