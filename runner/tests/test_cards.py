import random
from pathlib import Path
import pytest
from dixit_ai.cards import Card, Deck, ALL_CARDS, card_image_path

def test_all_cards_has_100():
    assert len(ALL_CARDS) == 100
    assert all(isinstance(c, Card) for c in ALL_CARDS)
    assert {c.id for c in ALL_CARDS} == set(range(1, 101))

def test_card_image_path_exists():
    # We need at least one card image to exist on disk for this test.
    p = card_image_path(1)
    assert p.exists(), f"missing {p}"
    assert p.suffix == ".jpg"

def test_deck_deals():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    hand = deck.deal(6)
    assert len(hand) == 6
    assert len({c.id for c in hand}) == 6
    assert len(deck.draw_pile) == 94

def test_deck_discard_and_reshuffle():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    # Drain it: deal 95 cards, discard 5, then trigger reshuffle.
    hands = [deck.deal(1)[0] for _ in range(95)]
    assert len(deck.draw_pile) == 5
    # Discard the first 50 cards.
    for c in hands[:50]:
        deck.discard.append(c)
    # Now draw 10 — should trigger reshuffle since draw_pile only has 5.
    drawn = []
    for _ in range(10):
        drawn.append(deck.draw_one())
    assert len(drawn) == 10
    assert all(d is not None for d in drawn)
    # After reshuffle, the discard becomes empty and the draw pile is rebuilt.
    # Specifically: started with draw=5 + discard=50 = 55 available.
    # We drew 10, so 45 remain.
    assert len(deck.draw_pile) == 45
    assert deck.discard == []

def test_deck_draw_when_truly_empty_returns_none():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    for _ in range(100):
        deck.draw_one()
    # Now everything is in `dealt` (caller's hands); discard is empty.
    assert deck.draw_one() is None

def test_deterministic_shuffle():
    a = Deck(rng=random.Random(1)).draw_one()
    b = Deck(rng=random.Random(1)).draw_one()
    assert a.id == b.id
