"""RandomPlayer: deterministic-random player used in tests and as a benchmark."""

from __future__ import annotations

import random

from dixit_ai.cards import Card, CardId


class RandomPlayer:
    """Picks legal moves uniformly at random. Never raises MoveError."""

    def __init__(
        self,
        model_id: str,
        seed: int = 0,
        display_name: str | None = None,
        org: str = "random",
    ) -> None:
        self.model_id = model_id
        self.display_name = display_name or model_id
        self.org = org
        self.previous_ids: list[str] = []
        self._rng = random.Random(seed)

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]:
        card = self._rng.choice(hand)
        clue = f"random clue {self._rng.randint(0, 9999)}"
        return card.id, clue

    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId:
        return self._rng.choice(hand).id

    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId:
        choices = [c for c in face_up_cards if c.id != own_card_id]
        return self._rng.choice(choices).id
