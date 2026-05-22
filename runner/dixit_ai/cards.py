"""Card metadata and the deck/discard machinery."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

CardId = int

REPO_ROOT = Path(__file__).resolve().parents[2]
CARDS_DIR = REPO_ROOT / "web" / "public" / "cards"


def card_image_path(card_id: CardId) -> Path:
    return CARDS_DIR / f"card_{card_id:05d}.jpg"


@dataclass(frozen=True)
class Card:
    id: CardId

    @property
    def image_path(self) -> Path:
        return card_image_path(self.id)


# Visual duplicates in the vendored deck (same illustration, different
# filenames). The engine treats them as distinct CardIds otherwise; remove
# them from the playable deck so a hand never contains two indistinguishable
# images. We keep the higher-resolution copy of each pair and drop the lower:
#   - 23 vs 24 (cat watching a yarn-ball moon): keep 23, drop 24
#   - 44 vs 45 (man on boat catching the moon): keep 44, drop 45
DUPLICATE_CARD_IDS: frozenset[CardId] = frozenset({24, 45})

ALL_CARDS: list[Card] = [
    Card(id=i) for i in range(1, 101) if i not in DUPLICATE_CARD_IDS
]


@dataclass
class Deck:
    """A 98-card deck with a discard pile that reshuffles back in when needed."""

    rng: random.Random = field(default_factory=random.Random)
    draw_pile: list[Card] = field(init=False)
    discard: list[Card] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.draw_pile = list(ALL_CARDS)
        self.rng.shuffle(self.draw_pile)

    def draw_one(self) -> Card | None:
        if not self.draw_pile:
            if not self.discard:
                return None
            # Reshuffle: discard becomes the new draw pile.
            self.draw_pile = self.discard
            self.discard = []
            self.rng.shuffle(self.draw_pile)
        return self.draw_pile.pop()

    def deal(self, n: int) -> list[Card]:
        out: list[Card] = []
        for _ in range(n):
            c = self.draw_one()
            if c is None:
                break
            out.append(c)
        return out
