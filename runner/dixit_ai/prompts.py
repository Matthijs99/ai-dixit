"""Prompt templates. Card images are appended by the adapter alongside labels."""

from __future__ import annotations


def build_system_prompt(
    *,
    my_model_id: str,
    my_display_name: str,
    lineup: list[str],
    display_names: dict[str, str],
    scoreboard: dict[str, int],
    turn_number: int,
) -> str:
    """Build a per-turn system prompt with rules and the current standings."""

    standings = sorted(
        lineup, key=lambda m: (-scoreboard.get(m, 0), m)
    )
    standings_lines = []
    for m in standings:
        marker = "  ← you" if m == my_model_id else ""
        standings_lines.append(
            f"  {display_names.get(m, m):22s} {scoreboard.get(m, 0):3d}{marker}"
        )

    return (
        f"You are playing a game of Dixit against four other AI models. "
        f"You are: {my_display_name}.\n"
        f"\n"
        f"GAME RULES\n"
        f"On each turn one player is the storyteller. They pick a card from their hand and give a one-line clue. "
        f"Each other player picks a card from their hand that matches the clue. "
        f"All cards are shuffled face-up. Non-storytellers vote for which card they think is the storyteller's.\n"
        f"\n"
        f"SCORING\n"
        f"- If everyone or no one votes for the storyteller's card: storyteller scores 0, every non-storyteller scores 2.\n"
        f"- Otherwise: storyteller and each correct voter score 3.\n"
        f"- Every non-storyteller scores +1 per vote their card received (capped at +3).\n"
        f"\n"
        f"Strategy: storytellers want clues that fool some but not all — too obvious or too obscure both score zero. "
        f"Non-storytellers want decoys that draw votes away from the storyteller's card.\n"
        f"\n"
        f"WIN CONDITION\n"
        f"First to 30 points wins. Game also ends at 50 turns total.\n"
        f"\n"
        f"CURRENT STANDINGS (turn {turn_number} of up to 50)\n"
        + "\n".join(standings_lines)
        + "\n"
        f"\n"
        f"You will see card images labeled A, B, C, ... Use those labels when responding. "
        f"Respond ONLY with the requested JSON; no prose outside it."
    )


def storyteller_user(labels: list[str]) -> str:
    label_lines = "\n".join(f"Card {L}: <image attached>" for L in labels)
    return (
        f"It is your turn to be the storyteller.\n\n"
        f"Here is your hand:\n{label_lines}\n\n"
        f"Pick one card and write a clue (a word, phrase, or sentence, up to 140 characters) "
        f"that evokes the card. Aim for subtle: too literal and everyone guesses (0 points); "
        f"too obscure and no one guesses (0 points).\n\n"
        f"Respond with JSON: {{\"card\": \"<label>\", \"clue\": \"<text>\"}}"
    )


def picker_user(labels: list[str], clue: str) -> str:
    label_lines = "\n".join(f"Card {L}: <image attached>" for L in labels)
    return (
        f"The storyteller's clue is:\n\n  \"{clue}\"\n\n"
        f"Here is your hand:\n{label_lines}\n\n"
        f"Pick the card from your hand that best matches the clue.\n\n"
        f"Respond with JSON: {{\"card\": \"<label>\"}}"
    )


def voter_user(labels: list[str], clue: str, own_label: str) -> str:
    label_lines = "\n".join(f"Card {L}: <image attached>" for L in labels)
    return (
        f"The storyteller's clue was:\n\n  \"{clue}\"\n\n"
        f"Here are the face-up cards:\n{label_lines}\n\n"
        f"You may NOT vote for label {own_label} — that is your own card. "
        f"Vote for the card you think is the storyteller's.\n\n"
        f"Respond with JSON: {{\"card\": \"<label>\"}}"
    )
