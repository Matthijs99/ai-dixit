from dixit_ai.prompts import (
    build_system_prompt,
    picker_user,
    storyteller_user,
    voter_user,
)


def _sample_system_prompt() -> str:
    return build_system_prompt(
        my_model_id="claude-opus-4-7",
        my_display_name="Claude Opus 4.7",
        lineup=["claude-opus-4-7", "gpt-5.5"],
        display_names={
            "claude-opus-4-7": "Claude Opus 4.7",
            "gpt-5.5": "GPT-5.5",
        },
        scoreboard={"claude-opus-4-7": 10, "gpt-5.5": 4},
        turn_number=5,
    )


def test_system_prompt_mentions_dixit():
    assert "Dixit" in _sample_system_prompt()


def test_system_prompt_includes_scoreboard():
    p = _sample_system_prompt()
    assert "Claude Opus 4.7" in p
    assert "GPT-5.5" in p
    # Numbers from the scoreboard
    assert "10" in p
    assert "4" in p
    # The self marker
    assert "← you" in p


def test_system_prompt_includes_rules():
    p = _sample_system_prompt()
    # 3-point and 2-point scoring rules surface
    assert "3" in p and "2" in p
    # Win condition
    assert "30" in p


def test_storyteller_user_lists_labels():
    text = storyteller_user(labels=["A", "B", "C", "D", "E", "F"])
    for L in "ABCDEF":
        assert f"Card {L}" in text
    assert "clue" in text.lower()


def test_picker_user_includes_clue():
    text = picker_user(labels=["A", "B"], clue="a soft wind")
    assert "a soft wind" in text
    assert "Card A" in text and "Card B" in text


def test_voter_user_excludes_own_card_label():
    text = voter_user(labels=["A", "B", "C", "D", "E"], clue="x", own_label="B")
    assert "B" in text
    assert "may not vote for" in text.lower() or "do not vote for" in text.lower()
