import pytest
from dixit_ai.cards import Card
from dixit_ai.players.base import (
    LabeledHand, MoveError, _label_hand, _validate_story,
    _validate_vote, StoryMove, VoteMove, BaseAdapter,
)


def test_label_hand_deterministic_with_seed():
    hand = [Card(id=i) for i in [11, 22, 33, 44, 55, 66]]
    a = _label_hand(hand, seed=1)
    b = _label_hand(hand, seed=1)
    assert a.labels == b.labels
    assert set(a.labels.values()) == {c.id for c in hand}

def test_label_hand_uses_prefix():
    hand = [Card(id=i) for i in [11, 22, 33]]
    lh = _label_hand(hand, seed=0)
    assert list(lh.labels.keys()) == ["A", "B", "C"]


def test_validate_story_legal():
    lh = LabeledHand(labels={"A": 11, "B": 22, "C": 33}, ordered_labels=["A","B","C"])
    move = StoryMove(card="A", clue="x")
    card_id, clue = _validate_story(move, lh)
    assert card_id == 11
    assert clue == "x"

def test_validate_story_illegal_label():
    lh = LabeledHand(labels={"A": 11, "B": 22}, ordered_labels=["A","B"])
    move = StoryMove(card="C", clue="x")
    with pytest.raises(ValueError):
        _validate_story(move, lh)

def test_validate_vote_blocks_self():
    lh = LabeledHand(labels={"A": 11, "B": 22, "C": 33}, ordered_labels=["A","B","C"])
    move = VoteMove(card="B")
    with pytest.raises(ValueError):
        _validate_vote(move, lh, own_card_id=22)


class StubAdapter(BaseAdapter):
    model_id = "stub"
    display_name = "stub"
    org = "test"

    def __init__(self, responses: list[str]):
        super().__init__()
        self.responses = list(responses)
        self.calls = 0

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        _ = (messages, schema, image_bytes_by_label)   # accept but ignore
        self.calls += 1
        return self.responses.pop(0)


def test_adapter_retries_once_then_raises():
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['{"card": "ZZZ"}', '{"card": "BAD"}'])
    with pytest.raises(MoveError):
        a.pick_for_clue(hand, "x")
    assert a.calls == 2


def test_adapter_succeeds_on_second_try():
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['not json', '{"card": "A"}'])
    chosen = a.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
    assert a.calls == 2


from unittest.mock import MagicMock
from dixit_ai.players.claude import ClaudePlayer

def test_claude_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]

    # Build a fake anthropic.Messages response with a tool_use block.
    fake_tool_use = MagicMock(type="tool_use", name="submit_move", input={"card": "A"})
    fake_msg = MagicMock(content=[fake_tool_use], stop_reason="tool_use")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    player = ClaudePlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "soft wind")
    assert chosen in {11, 22}
    fake_client.messages.create.assert_called_once()
