"""Player protocol + MoveError. Used by the engine and implemented by adapters."""

from __future__ import annotations

from typing import Protocol

from dixit_ai.cards import Card, CardId


class MoveError(Exception):
    """Raised by a Player when it fails to produce a valid move after retry."""


class Player(Protocol):
    model_id: str
    display_name: str
    org: str

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]: ...
    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId: ...
    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId: ...
