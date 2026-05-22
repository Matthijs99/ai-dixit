"""Game engine: pure Dixit rules. No LLM SDK imports."""

from __future__ import annotations

from typing import Mapping


ModelId = str
CardId = int


def score_turn(
    storyteller: ModelId,
    storyteller_card: CardId,
    submissions: Mapping[ModelId, CardId],
    votes: Mapping[ModelId, CardId],
) -> dict[ModelId, int]:
    """Apply Dixit scoring rules for a single turn.

    `submissions` maps every player who put a card on the table (including
    storyteller) to their card id. Pick forfeiters are omitted.

    `votes` maps every non-storyteller who voted to the card id they voted for.
    Vote forfeiters and pick forfeiters are omitted.

    Returns the delta for EVERY player named in `submissions`. Pick forfeiters
    are NOT in the result; the caller handles them with a zero delta.
    """
    delta: dict[ModelId, int] = {p: 0 for p in submissions}

    # Voters who participated (i.e., have a vote recorded).
    participants = [v for v in votes if v != storyteller]
    correct_votes = sum(1 for v in participants if votes[v] == storyteller_card)
    all_or_none = (
        participants
        and (correct_votes == 0 or correct_votes == len(participants))
    )

    if all_or_none:
        delta[storyteller] = 0
        for v in participants:
            delta[v] += 2
    else:
        delta[storyteller] = 3
        for v in participants:
            if votes[v] == storyteller_card:
                delta[v] += 3

    # Decoy bonus: every non-storyteller who submitted a card gets +1 per vote
    # their card received, capped at +3.
    for owner, card in submissions.items():
        if owner == storyteller:
            continue
        bonus = sum(1 for v_card in votes.values() if v_card == card)
        delta[owner] += min(bonus, 3)

    return delta
