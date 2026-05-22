import random
from dixit_ai.cards import ALL_CARDS, Card, Deck, DUPLICATE_CARD_IDS, card_image_path


# 100 source images on disk, 2 known visual duplicates removed.
EXPECTED_DECK_SIZE = 100 - len(DUPLICATE_CARD_IDS)


def test_all_cards_excludes_duplicates():
    assert len(ALL_CARDS) == EXPECTED_DECK_SIZE
    assert all(isinstance(c, Card) for c in ALL_CARDS)
    ids = {c.id for c in ALL_CARDS}
    # IDs are 1..100 minus the known duplicates.
    assert ids == set(range(1, 101)) - DUPLICATE_CARD_IDS
    # Sanity: the listed duplicates shouldn't appear.
    assert DUPLICATE_CARD_IDS.isdisjoint(ids)


def test_card_image_path_exists():
    p = card_image_path(1)
    assert p.exists(), f"missing {p}"
    assert p.suffix == ".jpg"


def test_deck_deals():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    hand = deck.deal(6)
    assert len(hand) == 6
    assert len({c.id for c in hand}) == 6
    assert len(deck.draw_pile) == EXPECTED_DECK_SIZE - 6


def test_deck_discard_and_reshuffle():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    # Drain it: deal all but 5 cards, then trigger reshuffle.
    leave_in_pile = 5
    take = EXPECTED_DECK_SIZE - leave_in_pile
    hands = [deck.deal(1)[0] for _ in range(take)]
    assert len(deck.draw_pile) == leave_in_pile
    # Discard the first 50 cards.
    for c in hands[:50]:
        deck.discard.append(c)
    # Now draw 10 — should trigger reshuffle since draw_pile only has 5.
    drawn = []
    for _ in range(10):
        drawn.append(deck.draw_one())
    assert len(drawn) == 10
    assert all(d is not None for d in drawn)
    # Started with draw=5 + discard=50 = 55 available; drew 10 → 45 remain.
    assert len(deck.draw_pile) == 45
    assert deck.discard == []


def test_deck_draw_when_truly_empty_returns_none():
    rng = random.Random(42)
    deck = Deck(rng=rng)
    for _ in range(EXPECTED_DECK_SIZE):
        deck.draw_one()
    assert deck.draw_one() is None


def test_deterministic_shuffle():
    a = Deck(rng=random.Random(1)).draw_one()
    b = Deck(rng=random.Random(1)).draw_one()
    assert a.id == b.id
