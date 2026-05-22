from dixit_ai.prompts import (
    storyteller_user,
    picker_user,
    voter_user,
    SYSTEM_PRELUDE,
)

def test_system_prelude_mentions_dixit():
    assert "Dixit" in SYSTEM_PRELUDE

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
    assert "B" in text  # mentioned somewhere
    assert "may not vote for" in text.lower() or "do not vote for" in text.lower()
