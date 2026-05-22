"""Prompt templates. Card images are appended by the adapter alongside labels."""

from __future__ import annotations

SYSTEM_PRELUDE = """You are an AI player in a game of Dixit. Dixit is a card game where players take turns being the storyteller. The storyteller picks one card from their hand and gives a clue — a word, phrase, or sentence — that evokes the card. Other players each pick a card from their hand that could also match the clue. All cards are shuffled face-up. Everyone but the storyteller votes for which card they think is the storyteller's.

Scoring rewards the storyteller for clues that are subtle: a clue too obvious or too obscure gives the storyteller zero. Decoys that fool others earn bonus points.

You will see card images labeled A, B, C, ... in each turn. Use those labels when responding. Respond ONLY with the requested JSON; no prose outside it."""


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
