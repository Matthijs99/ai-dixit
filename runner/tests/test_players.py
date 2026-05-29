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


def test_adapter_retries_up_to_max_attempts_then_raises():
    from dixit_ai.players.base import MAX_ATTEMPTS
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['{"card": "ZZZ"}'] * MAX_ATTEMPTS)
    with pytest.raises(MoveError):
        a.pick_for_clue(hand, "x")
    assert a.calls == MAX_ATTEMPTS


def test_adapter_succeeds_on_second_try():
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['not json', '{"card": "A"}'])
    chosen = a.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
    assert a.calls == 2


def test_adapter_sleeps_between_sdk_errors(monkeypatch):
    """SDK errors get a sleep between retries; validation errors do not."""
    from dixit_ai.players.base import (
        BaseAdapter,
        MAX_ATTEMPTS,
        MoveError,
        SDK_ERROR_BACKOFF_SECONDS,
    )

    sleeps: list[float] = []
    monkeypatch.setattr("dixit_ai.players.base.time.sleep", lambda s: sleeps.append(s))

    class RaisingAdapter(BaseAdapter):
        model_id = "stub"
        display_name = "stub"
        org = "test"

        def __init__(self):
            super().__init__()
            self.calls = 0

        def _call(self, **_):
            self.calls += 1
            raise RuntimeError("rate limit 429")

    hand = [Card(id=11), Card(id=22)]
    a = RaisingAdapter()
    with pytest.raises(MoveError):
        a.pick_for_clue(hand, "x")
    # MAX_ATTEMPTS calls, with a sleep between each consecutive pair (so MAX-1 sleeps).
    assert a.calls == MAX_ATTEMPTS
    assert len(sleeps) == MAX_ATTEMPTS - 1
    assert all(s == SDK_ERROR_BACKOFF_SECONDS for s in sleeps)


def test_adapter_no_sleep_on_validation_errors(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("dixit_ai.players.base.time.sleep", lambda s: sleeps.append(s))

    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['{"card": "ZZZ"}'] * 10)
    with pytest.raises(MoveError):
        a.pick_for_clue(hand, "x")
    # Validation errors should never trigger time.sleep.
    assert sleeps == []


from unittest.mock import MagicMock
from dixit_ai.players.claude import ClaudePlayer
from dixit_ai.players.openai import OpenAIPlayer

def test_claude_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]

    # Build a fake anthropic.Messages response with a tool_use block.
    fake_tool_use = MagicMock(type="tool_use", name="submit_move", input={"card": "A"})
    fake_msg = MagicMock(content=[fake_tool_use], stop_reason="tool_use")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    player = ClaudePlayer(
        model_id="claude-test", display_name="Claude Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "soft wind")
    assert chosen in {11, 22}
    fake_client.messages.create.assert_called_once()


def test_openai_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = OpenAIPlayer(
        model_id="gpt-test", display_name="GPT Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}


def test_mistral_adapter_returns_card_id_on_valid_response():
    from dixit_ai.players.mistral import MistralPlayer

    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.complete.return_value = fake_resp

    player = MistralPlayer(
        model_id="mistral-test", display_name="Mistral Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}


def test_grok_adapter_returns_card_id_on_valid_response():
    from dixit_ai.players.grok import GrokPlayer

    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = GrokPlayer(
        model_id="grok-test", display_name="Grok Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}


def test_bytedance_adapter_returns_card_id_on_valid_response():
    from dixit_ai.players.bytedance import BytedancePlayer

    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = BytedancePlayer(
        model_id="bytedance/seed-test", display_name="Seed Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
    assert player.org == "Bytedance"


def test_moonshot_adapter_returns_card_id_on_valid_response():
    from dixit_ai.players.moonshot import MoonshotPlayer

    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = MoonshotPlayer(
        model_id="kimi-test", display_name="Kimi Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
    assert player.org == "Moonshot"


def test_claude_thinking_uses_auto_tool_choice_and_thinking_param():
    hand = [Card(id=11), Card(id=22)]
    fake_tool_use = MagicMock(type="tool_use", name="submit_move", input={"card": "A"})
    fake_msg = MagicMock(content=[fake_tool_use], stop_reason="tool_use")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    player = ClaudePlayer(
        model_id="claude-test",
        display_name="Claude Test",
        thinking=True,
        client=fake_client,
    )
    chosen = player.pick_for_clue(hand, "soft wind")
    assert chosen in {11, 22}

    kwargs = fake_client.messages.create.call_args.kwargs
    # Forced tool use is incompatible with thinking → must be auto.
    assert kwargs["tool_choice"] == {"type": "auto"}
    # Opus 4.7: adaptive thinking + output_config.effort (no budget_tokens).
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"]["effort"] in {"low", "medium", "high", "xhigh", "max"}
    assert "budget_tokens" not in kwargs["thinking"]


def test_claude_without_thinking_forces_tool_choice():
    hand = [Card(id=11), Card(id=22)]
    fake_tool_use = MagicMock(type="tool_use", name="submit_move", input={"card": "A"})
    fake_msg = MagicMock(content=[fake_tool_use], stop_reason="tool_use")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    player = ClaudePlayer(
        model_id="claude-test", display_name="Claude Test", client=fake_client
    )
    player.pick_for_clue(hand, "x")
    kwargs = fake_client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "submit_move"}
    assert "thinking" not in kwargs


# ----- Smoke run -----

class _SmokePlayer:
    def __init__(self, model_id, ok):
        self.model_id = model_id
        self.display_name = model_id
        self._ok = ok

    def storytell(self, hand):
        if not self._ok:
            raise RuntimeError("boom")
        return (hand[0].id, "a clue")


def _run_smoke_with(monkeypatch, lineup):
    """Call runner.run_smoke() with a stubbed lineup, restoring base constants."""
    import dixit_ai.players as players_pkg
    from dixit_ai import runner
    from dixit_ai.players import base

    saved = (base.MAX_ATTEMPTS, base.SDK_ERROR_BACKOFF_SECONDS)
    monkeypatch.setattr(players_pkg, "default_lineup", lambda: lineup)
    try:
        return runner.run_smoke()
    finally:
        base.MAX_ATTEMPTS, base.SDK_ERROR_BACKOFF_SECONDS = saved


def test_run_smoke_fails_when_any_model_unreachable(monkeypatch):
    lineup = [_SmokePlayer("good", ok=True), _SmokePlayer("bad", ok=False)]
    assert _run_smoke_with(monkeypatch, lineup) == 1


def test_run_smoke_passes_when_all_models_callable(monkeypatch):
    lineup = [_SmokePlayer("good", ok=True), _SmokePlayer("also-good", ok=True)]
    assert _run_smoke_with(monkeypatch, lineup) == 0


def test_gemini_adapter_returns_card_id_on_valid_response(monkeypatch):
    import sys
    from dixit_ai.players.gemini import GeminiPlayer

    fake_part = MagicMock()
    fake_part.from_text = lambda text: ("text", text)
    fake_part.from_bytes = lambda data, mime_type: ("bytes", len(data))
    fake_types = MagicMock(Part=fake_part, GenerateContentConfig=lambda **k: k)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    hand = [Card(id=11), Card(id=22)]
    fake_resp = MagicMock(text='{"card": "A"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_resp

    player = GeminiPlayer(
        model_id="gemini-test", display_name="Gemini Test", client=fake_client
    )
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}


# ----- Loader tests -----

def test_load_roster_reads_yaml(tmp_path, monkeypatch):
    from dixit_ai.players import load_roster

    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        "players:\n"
        "  - adapter: openai\n"
        "    model_id: gpt-x\n"
        "    display_name: GPT X\n"
    )
    monkeypatch.setenv("DIXIT_MODELS_YAML", str(yaml_path))
    roster = load_roster()
    assert len(roster) == 1
    assert roster[0]["model_id"] == "gpt-x"
    assert roster[0]["display_name"] == "GPT X"


def test_default_lineup_instantiates_from_yaml(tmp_path, monkeypatch):
    from dixit_ai.players import default_lineup

    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        "players:\n"
        "  - adapter: openai\n"
        "    model_id: gpt-x\n"
        "    display_name: GPT X\n"
    )
    monkeypatch.setenv("DIXIT_MODELS_YAML", str(yaml_path))
    # Loader instantiates OpenAIPlayer which would need OPENAI_API_KEY.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    lineup = default_lineup()
    assert len(lineup) == 1
    assert lineup[0].model_id == "gpt-x"
    assert lineup[0].display_name == "GPT X"


def test_default_lineup_rejects_unknown_adapter(tmp_path, monkeypatch):
    from dixit_ai.players import default_lineup

    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        "players:\n"
        "  - adapter: nope\n"
        "    model_id: x\n"
        "    display_name: X\n"
    )
    monkeypatch.setenv("DIXIT_MODELS_YAML", str(yaml_path))
    with pytest.raises(ValueError, match="unknown adapter"):
        default_lineup()


def test_default_lineup_rejects_missing_fields(tmp_path, monkeypatch):
    from dixit_ai.players import default_lineup

    yaml_path = tmp_path / "models.yaml"
    yaml_path.write_text(
        "players:\n"
        "  - adapter: openai\n"
        "    model_id: gpt-x\n"
    )
    monkeypatch.setenv("DIXIT_MODELS_YAML", str(yaml_path))
    with pytest.raises(ValueError, match="display_name"):
        default_lineup()
