# AI Dixit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a system where five vision-capable LLMs (Claude, GPT, Gemini, Grok, Pixtral) play one full Dixit game per night in GitHub Actions; results commit to the repo as JSON, and a static Astro site renders a leaderboard (Elo) and per-game log.

**Architecture:** Two physically separated halves of the repo — a Python runner (engine + LLM adapters) and an Astro static site — meeting only through committed JSON files in `data/`. The engine has zero LLM SDK imports; each model is a thin adapter behind a `Player` protocol. Card images are presented as freshly shuffled labels per call so the model can't leak position info.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, anthropic/openai/google-genai/mistralai SDKs; Astro 4 (static output); GitHub Actions for both cron + Pages deploy.

**Spec:** `docs/superpowers/specs/2026-05-22-ai-dixit-design.md` — refer to this for any ambiguity.

---

## File map

```
ai-dixit/
├── runner/
│   ├── pyproject.toml
│   ├── dixit_ai/
│   │   ├── __init__.py
│   │   ├── __main__.py            # `python -m dixit_ai`
│   │   ├── cards.py               # Card, Deck (with discard + reshuffle)
│   │   ├── engine.py              # game loop, scoring, TurnRecord
│   │   ├── elo.py                 # pairwise Elo updates
│   │   ├── storage.py             # read/write data/*.json
│   │   ├── prompts.py             # prompt templates
│   │   ├── runner.py              # orchestrates a full game
│   │   └── players/
│   │       ├── __init__.py        # LINEUP constant
│   │       ├── base.py            # Player protocol + Pydantic moves + validation/retry
│   │       ├── random_player.py
│   │       ├── claude.py
│   │       ├── openai.py
│   │       ├── gemini.py
│   │       ├── grok.py
│   │       └── pixtral.py
│   └── tests/
│       ├── test_cards.py
│       ├── test_engine.py
│       ├── test_elo.py
│       ├── test_storage.py
│       └── test_players.py
├── web/
│   ├── package.json
│   ├── astro.config.mjs
│   ├── tsconfig.json
│   ├── public/cards/              # card_00001.jpg .. card_00100.jpg
│   └── src/
│       ├── pages/
│       │   ├── index.astro
│       │   └── games/[id].astro
│       ├── components/
│       │   ├── EloTable.astro
│       │   ├── TurnRow.astro
│       │   └── CardImage.astro
│       └── lib/data.ts
├── data/
│   ├── elo.json                   # bootstrapped at 1500
│   ├── index.json                 # bootstrapped at []
│   └── games/                     # populated by the runner
├── .github/workflows/
│   ├── nightly.yml
│   └── deploy.yml
└── README.md
```

Card source-of-truth: `web/public/cards/`. The runner reads images from there with a path computed relative to the repo root.

---

## Conventions

- All work happens from the repo root `/home/matthijs/git/dixit` unless noted.
- Tests use `pytest`. Run from `runner/` with `python -m pytest`.
- Every task ends in a single commit. Commit messages: imperative mood, ≤72 chars subject. End every commit body with `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.
- TDD throughout where the code has logic. Pure-config files (workflows, package.json) skip the test step.

---

## Task 1: Repo scaffolding & Python project

**Files:**
- Create: `runner/pyproject.toml`
- Create: `runner/dixit_ai/__init__.py` (empty)
- Create: `runner/tests/__init__.py` (empty)
- Create: `runner/tests/test_smoke.py`

- [ ] **Step 1: Write the smoke test**

`runner/tests/test_smoke.py`:

```python
import dixit_ai

def test_package_importable():
    assert dixit_ai is not None
```

- [ ] **Step 2: Create the empty package**

`runner/dixit_ai/__init__.py`:

```python
"""dixit_ai — nightly LLM Dixit league."""
__version__ = "0.1.0"
```

`runner/tests/__init__.py`: empty file.

- [ ] **Step 3: Create pyproject.toml**

`runner/pyproject.toml`:

```toml
[project]
name = "dixit-ai"
version = "0.1.0"
description = "Nightly LLM Dixit league."
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.6",
  "anthropic>=0.40",
  "openai>=1.50",
  "google-genai>=0.3",
  "mistralai>=1.2",
  "pillow>=10",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-mock>=3.12"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["dixit_ai*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 4: Install editable + verify test passes**

Run from `runner/`:

```bash
cd runner && pip install -e ".[dev]"
python -m pytest -v
```

Expected: `1 passed`. The smoke test confirms the package imports.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/
git commit -m "$(cat <<'EOF'
Scaffold Python runner package

Create runner/ subproject with pyproject.toml declaring the five SDK
dependencies (anthropic, openai, google-genai, mistralai, pillow) plus
pydantic and pytest. Smoke test confirms dixit_ai is importable.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Vendor 100 card images

**Files:**
- Create: `web/public/cards/card_00001.jpg` … `card_00100.jpg`

These images come from `jminuscula/dixit-online`'s `cards/` directory. We commit them once; they never change.

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /home/matthijs/git/dixit/web/public/cards
```

- [ ] **Step 2: Download all 100 cards in parallel**

```bash
cd /home/matthijs/git/dixit/web/public/cards
for i in $(seq -f "%05g" 1 100); do
  curl -sSfL "https://raw.githubusercontent.com/jminuscula/dixit-online/master/cards/card_$i.jpg" -o "card_$i.jpg" &
done
wait
ls | wc -l   # expect 100
ls card_00100.jpg && ls card_00001.jpg   # spot-check ends
```

Expected: `100` and both files exist.

- [ ] **Step 3: Verify they're real JPEGs**

```bash
file /home/matthijs/git/dixit/web/public/cards/card_00050.jpg
```

Expected: `... JPEG image data ...`

- [ ] **Step 4: Commit**

```bash
cd /home/matthijs/git/dixit
git add web/public/cards/
git commit -m "$(cat <<'EOF'
Vendor 100 Dixit card images from jminuscula/dixit-online

Cards live under web/public/cards/ so the Astro site serves them as
static assets. The Python runner reads them directly from the same path
relative to the repo root. Total ~3 MB.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Card types and Deck with reshuffle

**Files:**
- Create: `runner/dixit_ai/cards.py`
- Create: `runner/tests/test_cards.py`

- [ ] **Step 1: Write failing tests**

`runner/tests/test_cards.py`:

```python
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
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_cards.py -v
```

Expected: `ModuleNotFoundError: No module named 'dixit_ai.cards'`

- [ ] **Step 3: Implement `cards.py`**

`runner/dixit_ai/cards.py`:

```python
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


ALL_CARDS: list[Card] = [Card(id=i) for i in range(1, 101)]


@dataclass
class Deck:
    """A 100-card deck with a discard pile that reshuffles back in when needed."""

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
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_cards.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/cards.py runner/tests/test_cards.py
git commit -m "$(cat <<'EOF'
Add Card and Deck primitives with reshuffle

The Deck shuffles the discard pile back into the draw pile when the draw
pile is empty, which matches the spec's reshuffle rule. Card.id maps to a
file under web/public/cards/. RNG is injectable for deterministic tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Engine scoring

**Files:**
- Create: `runner/dixit_ai/engine.py` (scoring portion only — game loop in Task 5)
- Create: `runner/tests/test_engine.py`

- [ ] **Step 1: Write scoring tests**

`runner/tests/test_engine.py`:

```python
from dixit_ai.engine import score_turn

# Each test specifies:
#   storyteller: model_id
#   storyteller_card: int
#   submissions: {model: card_id} — does NOT need to include storyteller; engine adds it
#   votes: {voter: voted_card_id} — only non-storytellers; missing voter = vote forfeit
#   expected: {model: delta}

def test_partial_correct_votes():
    # Storyteller card = 1. Two voters guess 1, two guess decoys.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 2, "D": 3}
    delta = score_turn("S", 1, submissions, votes)
    # Storyteller gets 3 (some but not all guessed correctly)
    # A, B guessed correctly → 3 each
    # C, D guessed wrong → 0 base
    # Decoy bonuses: card 2 got 1 vote → A gets +1; card 3 got 1 vote → B gets +1.
    assert delta == {"S": 3, "A": 3 + 1, "B": 3 + 1, "C": 0, "D": 0}

def test_all_correct_votes():
    # All 4 non-storytellers vote for the storyteller's card → storyteller gets 0,
    # everyone else gets 2.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 1, "D": 1}
    delta = score_turn("S", 1, submissions, votes)
    assert delta == {"S": 0, "A": 2, "B": 2, "C": 2, "D": 2}

def test_no_correct_votes():
    # None voted for storyteller's card.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 2, "B": 3, "C": 4, "D": 5}
    # A→2 (B's card), B→3 (A's card), C→4 (C's own? no — C can't vote for own)
    # Adjust: use legal votes only.
    votes = {"A": 3, "B": 2, "C": 5, "D": 4}
    delta = score_turn("S", 1, submissions, votes)
    # Storyteller: 0 (no one guessed).
    # Each voter: 0 base.
    # Decoy bonuses: card 2 got 1 vote (B); card 3 got 1 vote (A);
    # card 4 got 1 vote (D); card 5 got 1 vote (C).
    assert delta == {"S": 0, "A": 0 + 1, "B": 0 + 1, "C": 0 + 1, "D": 0 + 1}

def test_decoy_bonus_capped_at_3():
    # Construct a 6-player hypothetical to force a decoy bonus >3.
    # In the real game N=5, but score_turn is general.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5, "E": 6}
    # All 5 voters guess card 2 (A's decoy). Cap kicks in.
    votes = {"A": 1, "B": 2, "C": 2, "D": 2, "E": 2}
    # Wait — A guessed correctly (1), so storyteller is NOT all-or-none.
    # Storyteller gets 3, A gets 3.
    # Decoy bonus for card 2: 4 votes → A gets +3 (capped).
    delta = score_turn("S", 1, submissions, votes)
    assert delta["A"] == 3 + 3
    assert delta["S"] == 3

def test_vote_forfeit_excluded_from_denominator():
    # 4 non-storytellers, but D forfeited their vote.
    # Among the 3 who voted: all 3 voted correctly → all-or-none applies → storyteller 0, others 2.
    # D (forfeit) gets 0 plus any decoy bonus.
    submissions = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}
    votes = {"A": 1, "B": 1, "C": 1}  # D missing
    delta = score_turn("S", 1, submissions, votes)
    assert delta == {"S": 0, "A": 2, "B": 2, "C": 2, "D": 0}

def test_pick_forfeit_no_card_no_decoy_bonus():
    # A forfeited their pick: not in submissions, not in votes.
    submissions = {"S": 1, "B": 3, "C": 4, "D": 5}  # A omitted
    votes = {"B": 1, "C": 3, "D": 4}  # A omitted
    delta = score_turn("S", 1, submissions, votes)
    # Among participants (B, C, D): only B voted correctly → partial → storyteller 3, B 3.
    # Decoy bonus: card 3 got 1 vote → B +1; card 4 got 1 vote → C +1.
    assert delta == {"S": 3, "B": 3 + 1, "C": 0 + 1, "D": 0, "A": 0}
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_engine.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement scoring**

`runner/dixit_ai/engine.py`:

```python
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

    Returns the delta for EVERY player named in either map. Pick forfeiters
    that are otherwise expected to be tallied must be added by the caller via
    a zero-delta sentinel — easiest is to pre-populate the result.
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
```

- [ ] **Step 4: Run scoring tests — expect all pass**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_engine.py -v
```

Expected: `6 passed`.

The `test_pick_forfeit_no_card_no_decoy_bonus` test asserts `delta["A"] == 0` but A isn't in `submissions`. Look at the implementation: it pre-populates `delta` from `submissions` only. So `delta["A"]` would raise `KeyError`.

Fix the test (the engine never reports forfeiters; the caller handles them):

```python
def test_pick_forfeit_no_card_no_decoy_bonus():
    submissions = {"S": 1, "B": 3, "C": 4, "D": 5}
    votes = {"B": 1, "C": 3, "D": 4}
    delta = score_turn("S", 1, submissions, votes)
    assert "A" not in delta
    assert delta == {"S": 3, "B": 3 + 1, "C": 0 + 1, "D": 0}
```

Re-run; expect all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/engine.py runner/tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add Dixit scoring function

score_turn() implements all four cases: partial-correct (3+3), all-correct
(0/2), no-correct (0/0+decoys), and the +1/+3 decoy bonus. Forfeiters
(missing from submissions or votes) are excluded from both the all-or-none
denominator and from the result map — the caller is responsible for the
overall scoreboard.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Engine game loop with mocks

**Files:**
- Modify: `runner/dixit_ai/engine.py` (append the game loop)
- Modify: `runner/tests/test_engine.py` (append loop tests)
- Create: `runner/dixit_ai/players/__init__.py` (empty for now)
- Create: `runner/dixit_ai/players/base.py` (just the Player protocol + MoveError)
- Create: `runner/dixit_ai/players/random_player.py`

- [ ] **Step 1: Write the Player protocol**

`runner/dixit_ai/players/__init__.py`: empty.

`runner/dixit_ai/players/base.py`:

```python
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
```

`runner/dixit_ai/players/random_player.py`:

```python
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
```

- [ ] **Step 2: Write game loop tests**

Append to `runner/tests/test_engine.py`:

```python
import random
from dixit_ai.engine import play_game, TurnRecord, GameResult
from dixit_ai.players.random_player import RandomPlayer

def make_random_players(n: int = 5, base_seed: int = 100) -> list[RandomPlayer]:
    return [RandomPlayer(model_id=f"r{i}", seed=base_seed + i) for i in range(n)]

def test_game_terminates_under_turn_cap():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    assert isinstance(result, GameResult)
    assert len(result.turns) <= 50
    assert result.status in {"complete", "turn_limit"}
    assert set(result.final_scores.keys()) == {p.model_id for p in players}

def test_game_winner_has_highest_score():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    winner = result.winner
    assert winner is not None
    assert result.final_scores[winner] == max(result.final_scores.values())

def test_determinism_with_same_seed():
    a = play_game(make_random_players(), rng_seed="x")
    b = play_game(make_random_players(), rng_seed="x")
    assert a.final_scores == b.final_scores
    assert a.status == b.status
    assert [t.turn for t in a.turns] == [t.turn for t in b.turns]

def test_hands_stay_at_size_six():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    # The engine should never have left a player with fewer than 6 cards mid-game,
    # because reshuffling keeps the deck non-empty.
    for snap in result.hand_size_snapshots:
        for size in snap.values():
            assert size == 6, f"hand shrank to {size}"

def test_storyteller_rotates():
    players = make_random_players(3)  # 3 players, easier to verify rotation
    result = play_game(players, rng_seed="test")
    expected_storytellers = [players[i % 3].model_id for i in range(len(result.turns))]
    actual = [t.storyteller for t in result.turns]
    assert actual == expected_storytellers

def test_face_up_order_includes_storyteller_card():
    players = make_random_players()
    result = play_game(players, rng_seed="test")
    for t in result.turns:
        if t.face_up_order:
            assert t.storyteller_card in t.face_up_order
```

- [ ] **Step 3: Run tests — expect import failure for `play_game`**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_engine.py -v
```

Expected: ImportError for `play_game`, `TurnRecord`, `GameResult`.

- [ ] **Step 4: Implement the game loop**

Append to `runner/dixit_ai/engine.py`:

```python
import random
from dataclasses import dataclass, field
from typing import Sequence

from dixit_ai.cards import Card, CardId, Deck
from dixit_ai.players.base import MoveError, Player


HAND_SIZE = 6
WIN_SCORE = 30
TURN_LIMIT = 50


@dataclass
class TurnRecord:
    turn: int
    storyteller: ModelId
    clue: str | None
    storyteller_card: CardId | None
    submissions: dict[ModelId, CardId]
    face_up_order: list[CardId]
    votes: dict[ModelId, CardId]
    scores_delta: dict[ModelId, int]
    scores_total: dict[ModelId, int]
    degraded: list[str] = field(default_factory=list)


@dataclass
class GameResult:
    turns: list[TurnRecord]
    final_scores: dict[ModelId, int]
    winner: ModelId | None
    status: str   # "complete" or "turn_limit"
    hand_size_snapshots: list[dict[ModelId, int]] = field(default_factory=list)


def play_game(players: Sequence[Player], rng_seed: str = "default") -> GameResult:
    """Play one full Dixit game and return a GameResult."""

    rng = random.Random(rng_seed)
    deck = Deck(rng=rng)
    hands: dict[ModelId, list[Card]] = {p.model_id: deck.deal(HAND_SIZE) for p in players}
    totals: dict[ModelId, int] = {p.model_id: 0 for p in players}
    turns: list[TurnRecord] = []
    hand_snapshots: list[dict[ModelId, int]] = []

    by_id = {p.model_id: p for p in players}
    order = [p.model_id for p in players]

    turn_index = 0
    status = "turn_limit"

    while turn_index < TURN_LIMIT:
        if any(score >= WIN_SCORE for score in totals.values()):
            status = "complete"
            break

        storyteller_id = order[turn_index % len(order)]
        storyteller = by_id[storyteller_id]

        record = TurnRecord(
            turn=turn_index,
            storyteller=storyteller_id,
            clue=None,
            storyteller_card=None,
            submissions={},
            face_up_order=[],
            votes={},
            scores_delta={p: 0 for p in totals},
            scores_total=dict(totals),
            degraded=[],
        )

        # a. Storyteller move.
        try:
            story_card_id, clue = storyteller.storytell(list(hands[storyteller_id]))
        except MoveError:
            record.degraded.append(f"{storyteller_id}:storytell:forfeit")
            turns.append(record)
            hand_snapshots.append({m: len(h) for m, h in hands.items()})
            turn_index += 1
            continue

        # Validate storyteller's card is in their hand.
        if not any(c.id == story_card_id for c in hands[storyteller_id]):
            record.degraded.append(f"{storyteller_id}:storytell:illegal")
            turns.append(record)
            hand_snapshots.append({m: len(h) for m, h in hands.items()})
            turn_index += 1
            continue

        record.clue = clue
        record.storyteller_card = story_card_id
        record.submissions[storyteller_id] = story_card_id

        # b. Other players pick.
        for pid in order:
            if pid == storyteller_id:
                continue
            try:
                picked = by_id[pid].pick_for_clue(list(hands[pid]), clue)
            except MoveError:
                record.degraded.append(f"{pid}:pick:forfeit")
                continue
            if not any(c.id == picked for c in hands[pid]):
                record.degraded.append(f"{pid}:pick:illegal")
                continue
            record.submissions[pid] = picked

        # c. Shuffle face-up reveal order.
        face_up_ids = list(record.submissions.values())
        rng.shuffle(face_up_ids)
        record.face_up_order = face_up_ids
        face_up_cards = [Card(id=cid) for cid in face_up_ids]

        # d. Voting.
        for pid in order:
            if pid == storyteller_id:
                continue
            if pid not in record.submissions:
                continue   # this player sat out the whole turn
            own_card = record.submissions[pid]
            try:
                voted = by_id[pid].vote(face_up_cards, clue, own_card)
            except MoveError:
                record.degraded.append(f"{pid}:vote:forfeit")
                continue
            if voted not in face_up_ids or voted == own_card:
                record.degraded.append(f"{pid}:vote:illegal")
                continue
            record.votes[pid] = voted

        # e. Score.
        delta = score_turn(storyteller_id, story_card_id, record.submissions, record.votes)
        # Pre-populate delta for any player not in submissions (pick forfeiters).
        for pid in order:
            delta.setdefault(pid, 0)
            totals[pid] += delta[pid]
        record.scores_delta = delta
        record.scores_total = dict(totals)

        # f. Played cards → discard.
        for cid in record.submissions.values():
            deck.discard.append(Card(id=cid))
            # Also remove from the owner's hand.
        for pid, played in record.submissions.items():
            hands[pid] = [c for c in hands[pid] if c.id != played]

        # g. Refill each hand to HAND_SIZE.
        for pid in order:
            while len(hands[pid]) < HAND_SIZE:
                c = deck.draw_one()
                if c is None:
                    break
                hands[pid].append(c)

        turns.append(record)
        hand_snapshots.append({m: len(h) for m, h in hands.items()})
        turn_index += 1

    winner = max(totals, key=lambda p: totals[p]) if totals else None
    return GameResult(
        turns=turns,
        final_scores=dict(totals),
        winner=winner,
        status=status,
        hand_size_snapshots=hand_snapshots,
    )
```

- [ ] **Step 5: Run engine tests — expect all pass**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_engine.py -v
```

Expected: all 6 scoring tests + 6 game-loop tests pass (`12 passed`).

If any fail, fix iteratively. Common pitfalls:
- The `score_turn` call returns a dict only for participants; the loop has to pre-populate zeros for forfeiters before adding to `totals`.
- `face_up_order` shuffle uses `rng`, so the order is deterministic per seed.

- [ ] **Step 6: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/engine.py runner/dixit_ai/players/ runner/tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add game loop, Player protocol, and RandomPlayer

The engine wraps each player call in try/except MoveError and records
forfeits in the TurnRecord.degraded list rather than substituting random
moves. Illegal moves (card not in hand, vote-for-self) are treated as
forfeits too. RandomPlayer is the deterministic baseline used in tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Forfeit semantics tests

**Files:**
- Modify: `runner/tests/test_engine.py`

The game loop already implements forfeit handling. This task locks the
semantics down with targeted tests.

- [ ] **Step 1: Write failing tests**

Append to `runner/tests/test_engine.py`:

```python
from dixit_ai.players.base import MoveError

class ForfeitingStoryteller:
    model_id = "F"
    display_name = "F"
    org = "test"

    def __init__(self, forfeit_phase: str):
        self.phase = forfeit_phase

    def storytell(self, hand):
        if self.phase == "storytell":
            raise MoveError("nope")
        return hand[0].id, "clue"

    def pick_for_clue(self, hand, clue):
        if self.phase == "pick":
            raise MoveError("nope")
        return hand[0].id

    def vote(self, face_up_cards, clue, own_card_id):
        if self.phase == "vote":
            raise MoveError("nope")
        choices = [c for c in face_up_cards if c.id != own_card_id]
        return choices[0].id


def make_mixed_players(forfeit_phase: str):
    # F always forfeits at the given phase. Others are RandomPlayers.
    return [
        ForfeitingStoryteller(forfeit_phase),
        RandomPlayer(model_id="a", seed=1),
        RandomPlayer(model_id="b", seed=2),
        RandomPlayer(model_id="c", seed=3),
        RandomPlayer(model_id="d", seed=4),
    ]


def test_storyteller_forfeit_skips_turn():
    players = make_mixed_players("storytell")
    result = play_game(players, rng_seed="seed1")
    # Every turn where F was storyteller should have degraded contain
    # "F:storytell:forfeit" and have empty submissions/votes.
    forfeits = [t for t in result.turns if "F:storytell:forfeit" in t.degraded]
    assert forfeits, "expected at least one storyteller forfeit"
    for t in forfeits:
        assert t.submissions == {}
        assert t.votes == {}
        assert t.clue is None
        assert all(d == 0 for d in t.scores_delta.values())


def test_pick_forfeit_removes_from_submissions_and_votes():
    players = make_mixed_players("pick")
    result = play_game(players, rng_seed="seed2")
    # Find any turn where F was NOT storyteller (i.e. F was supposed to pick).
    f_pick_turns = [t for t in result.turns if t.storyteller != "F" and "F:pick:forfeit" in t.degraded]
    assert f_pick_turns
    for t in f_pick_turns:
        assert "F" not in t.submissions
        assert "F" not in t.votes


def test_vote_forfeit_keeps_submission_omits_vote():
    players = make_mixed_players("vote")
    result = play_game(players, rng_seed="seed3")
    f_vote_turns = [t for t in result.turns if t.storyteller != "F" and "F:vote:forfeit" in t.degraded]
    assert f_vote_turns
    for t in f_vote_turns:
        assert "F" in t.submissions
        assert "F" not in t.votes
```

- [ ] **Step 2: Run tests**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_engine.py -k forfeit -v
```

Expected: all 3 pass. The engine already supports forfeits; these tests are coverage, not new behavior.

- [ ] **Step 3: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/tests/test_engine.py
git commit -m "$(cat <<'EOF'
Add forfeit semantics tests for all three phases

Storyteller forfeit skips the whole turn; pick forfeit removes the player
from submissions and votes; vote forfeit keeps the submission and only
drops the vote.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Elo module

**Files:**
- Create: `runner/dixit_ai/elo.py`
- Create: `runner/tests/test_elo.py`

- [ ] **Step 1: Write tests**

`runner/tests/test_elo.py`:

```python
from dixit_ai.elo import expected_score, update_ratings, K

def test_expected_score_equal_ratings():
    assert abs(expected_score(1500, 1500) - 0.5) < 1e-9

def test_expected_score_higher_rated_favored():
    # A rated 100 above B: E_A should be > 0.5.
    e_a = expected_score(1600, 1500)
    assert 0.5 < e_a < 1.0

def test_pairwise_update_winner_gains():
    # placements: A=1st, B=2nd
    ratings = {"A": 1500, "B": 1500}
    placements = ["A", "B"]
    new = update_ratings(ratings, placements)
    assert new["A"] > 1500
    assert new["B"] < 1500
    # K=32 with equal ratings: winner +16, loser -16.
    assert round(new["A"] - 1500) == 16
    assert round(1500 - new["B"]) == 16

def test_total_delta_is_zero():
    ratings = {"A": 1500, "B": 1450, "C": 1550, "D": 1400, "E": 1600}
    placements = ["C", "A", "E", "B", "D"]
    new = update_ratings(ratings, placements)
    delta_sum = sum(new[m] - ratings[m] for m in ratings)
    assert abs(delta_sum) < 1e-6, f"delta sum drift: {delta_sum}"

def test_five_player_sweep_top_gains_about_50():
    ratings = {f"p{i}": 1500 for i in range(5)}
    placements = [f"p{i}" for i in range(5)]
    new = update_ratings(ratings, placements)
    # Top finisher beats 4 equal-rated opponents → 4 * K * (1 - 0.5) = 64.
    # Bottom loses to 4: -64.
    assert round(new["p0"] - 1500) == 64
    assert round(1500 - new["p4"]) == 64

def test_symmetry_same_rating_same_placement():
    # Two players with identical ratings and identical placement (a tie) get identical updates.
    # Our model has no ties — the caller breaks them — so we instead test that
    # adjacent placements with identical ratings yield symmetric deltas.
    ratings = {"A": 1500, "B": 1500, "C": 1500}
    new = update_ratings(ratings, ["A", "B", "C"])
    # A finished above B and C; B above C.
    # The middle player B has 1 win (vs C) and 1 loss (vs A): net 0.
    assert round(new["B"] - 1500) == 0
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_elo.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement Elo**

`runner/dixit_ai/elo.py`:

```python
"""Placement-based pairwise Elo updates (K=32)."""

from __future__ import annotations

from typing import Mapping, Sequence

K = 32.0


def expected_score(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected-score formula."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    ratings: Mapping[str, float],
    placements: Sequence[str],
) -> dict[str, float]:
    """Apply pairwise Elo updates over all pairs (i, j) where i finished above j.

    `placements` is the ordering from 1st place to last.
    Returns a new dict with updated ratings; the input is not mutated.
    """
    new = {m: float(r) for m, r in ratings.items()}
    n = len(placements)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = placements[i], placements[j]
            e_a = expected_score(new[a], new[b])
            # Treating each pairwise comparison as a fresh game so deltas
            # accumulate.
            new[a] += K * (1 - e_a)
            new[b] += K * (0 - (1 - e_a))
    return new
```

Note: when we update incrementally, the second pair sees the post-update rating from the first pair. For multiplayer Elo this is a known choice — some use frozen pre-game ratings for all pairs. Using post-update ratings biases toward stability (less drift) and matches my spec mention of "10 pairwise updates per game". Tests are written against incremental.

Actually re-examine `test_five_player_sweep_top_gains_about_50`. With incremental updates:
- p0 vs p1: p0 wins, both at 1500 → p0 +16, p1 -16 → p0=1516, p1=1484
- p0 vs p2: p0=1516 vs p2=1500 → E_p0 ≈ 0.523 → p0 += K*(1-0.523)=15.3 → p0=1531.3, p2=1484.7
- ... etc

The top model ends up around 1500+50 not exactly +64. The test asserts `== 64`, which is only right under the "frozen ratings" approach. Let me clarify.

Let me commit to frozen ratings:

```python
def update_ratings(
    ratings: Mapping[str, float],
    placements: Sequence[str],
) -> dict[str, float]:
    new = {m: float(r) for m, r in ratings.items()}
    base = dict(new)   # snapshot
    n = len(placements)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = placements[i], placements[j]
            e_a = expected_score(base[a], base[b])
            new[a] += K * (1 - e_a)
            new[b] += K * (0 - (1 - e_a))
    return new
```

This makes the math match `test_five_player_sweep_top_gains_about_50` (top gains 4×16=64). Use this version.

- [ ] **Step 4: Run tests — all pass**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_elo.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/elo.py runner/tests/test_elo.py
git commit -m "$(cat <<'EOF'
Add placement-based pairwise Elo with frozen-rating pairs

K=32, standard expected-score formula. For each game, every pair (i,j)
where i finished above j gets one update; pairs use the pre-game ratings
(frozen) so per-pair deltas don't depend on update order. Total delta
across the field sums to zero.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Storage module

**Files:**
- Create: `runner/dixit_ai/storage.py`
- Create: `runner/tests/test_storage.py`

- [ ] **Step 1: Write tests**

`runner/tests/test_storage.py`:

```python
import json
from pathlib import Path
import pytest

from dixit_ai.storage import (
    DATA_DIR, load_elo, save_elo, load_index, append_index,
    save_game, game_exists,
)

def test_data_dir_resolves_to_repo_data(tmp_path, monkeypatch):
    # We patch DATA_DIR so we don't touch the real data/.
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    assert tmp_path.exists()

def test_save_and_load_elo(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    payload = {
        "updated_at": "2026-05-22T03:14:00Z",
        "models": {
            "m1": {"display_name": "M1", "org": "X", "rating": 1500, "games": 0, "wins": 0},
        },
    }
    save_elo(payload)
    assert (tmp_path / "elo.json").exists()
    loaded = load_elo()
    assert loaded == payload

def test_append_index_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "index.json").write_text("[]")
    row = {"game_id": "2026-05-22", "status": "complete"}
    append_index(row)
    rows = load_index()
    assert rows == [row]

def test_save_game_writes_two_files(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    save_game(
        game_id="2026-05-22",
        game_doc={"game_id": "2026-05-22", "turns": []},
        raw_lines=[{"foo": "bar"}],
    )
    assert (tmp_path / "games" / "2026-05-22.json").exists()
    raw = (tmp_path / "games" / "2026-05-22.raw.jsonl").read_text().splitlines()
    assert len(raw) == 1
    assert json.loads(raw[0]) == {"foo": "bar"}

def test_save_game_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    save_game(game_id="2026-05-22", game_doc={"x": 1}, raw_lines=[])
    with pytest.raises(FileExistsError):
        save_game(game_id="2026-05-22", game_doc={"x": 2}, raw_lines=[])

def test_game_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    assert not game_exists("2026-05-22")
    save_game(game_id="2026-05-22", game_doc={"x": 1}, raw_lines=[])
    assert game_exists("2026-05-22")
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_storage.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement storage**

`runner/dixit_ai/storage.py`:

```python
"""Read/write the JSON files in data/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dixit_ai.cards import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def load_elo() -> dict:
    return _read_json(DATA_DIR / "elo.json")


def save_elo(payload: dict) -> None:
    _write_json(DATA_DIR / "elo.json", payload)


def load_index() -> list:
    path = DATA_DIR / "index.json"
    if not path.exists():
        return []
    return _read_json(path)


def append_index(row: dict) -> None:
    rows = load_index()
    rows.append(row)
    _write_json(DATA_DIR / "index.json", rows)


def game_exists(game_id: str) -> bool:
    return (DATA_DIR / "games" / f"{game_id}.json").exists()


def save_game(*, game_id: str, game_doc: dict, raw_lines: list[dict]) -> None:
    games_dir = DATA_DIR / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    game_path = games_dir / f"{game_id}.json"
    raw_path = games_dir / f"{game_id}.raw.jsonl"
    if game_path.exists():
        raise FileExistsError(f"refusing to overwrite {game_path}")
    _write_json(game_path, game_doc)
    raw_path.write_text("".join(json.dumps(line) + "\n" for line in raw_lines))
```

- [ ] **Step 4: Run tests**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_storage.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/storage.py runner/tests/test_storage.py
git commit -m "$(cat <<'EOF'
Add data/ storage helpers

load/save for elo.json, index.json append, save_game writes both the
game doc and the raw audit jsonl together. save_game refuses to
overwrite an existing date — re-runs must explicitly delete first.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Bootstrap data files

**Files:**
- Create: `data/elo.json`
- Create: `data/index.json`
- Create: `data/games/.gitkeep`

- [ ] **Step 1: Write bootstrap files by hand**

```bash
mkdir -p /home/matthijs/git/dixit/data/games
touch /home/matthijs/git/dixit/data/games/.gitkeep
```

`data/elo.json`:

```json
{
  "updated_at": "2026-05-22T00:00:00Z",
  "models": {
    "claude-opus-4-7":  {"display_name": "Claude Opus 4.7",  "org": "Anthropic", "rating": 1500, "games": 0, "wins": 0},
    "gpt-5":            {"display_name": "GPT-5",            "org": "OpenAI",    "rating": 1500, "games": 0, "wins": 0},
    "gemini-2.5-pro":   {"display_name": "Gemini 2.5 Pro",   "org": "Google",    "rating": 1500, "games": 0, "wins": 0},
    "grok-4":           {"display_name": "Grok 4",           "org": "xAI",       "rating": 1500, "games": 0, "wins": 0},
    "pixtral-large":    {"display_name": "Pixtral Large",    "org": "Mistral",   "rating": 1500, "games": 0, "wins": 0}
  }
}
```

`data/index.json`:

```json
[]
```

- [ ] **Step 2: Verify storage helpers can read them**

```bash
cd /home/matthijs/git/dixit/runner
python -c "from dixit_ai.storage import load_elo, load_index; print(load_elo()['models']['gpt-5']); print(load_index())"
```

Expected: prints the gpt-5 row dict and `[]`.

- [ ] **Step 3: Commit**

```bash
cd /home/matthijs/git/dixit
git add data/
git commit -m "$(cat <<'EOF'
Bootstrap data/ with all five models at Elo 1500

Hand-written initial state. Once a game runs, the runner takes over and
rewrites these files. data/games/.gitkeep keeps the dir present in git.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Prompts module

**Files:**
- Create: `runner/dixit_ai/prompts.py`
- Create: `runner/tests/test_prompts.py`

- [ ] **Step 1: Write tests**

`runner/tests/test_prompts.py`:

```python
from dixit_ai.prompts import (
    storyteller_system,
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
```

- [ ] **Step 2: Run tests — import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_prompts.py -v
```

- [ ] **Step 3: Implement prompts**

`runner/dixit_ai/prompts.py`:

```python
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
        f"Respond with JSON: {{\"card\": \"<label>\", \"reasoning\": \"<optional short text>\"}}"
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_prompts.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/prompts.py runner/tests/test_prompts.py
git commit -m "$(cat <<'EOF'
Add shared prompt templates for storytell/pick/vote phases

Single source of truth for the strings each adapter sends. Card images
are referenced by label and attached by the adapter; the prompt text
references them as 'Card A: <image attached>' etc.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Adapter base — labeling, schemas, validation, retry

**Files:**
- Modify: `runner/dixit_ai/players/base.py`
- Create: `runner/tests/test_players.py`

This task adds the heavy lifting shared by all five adapters: label assignment, Pydantic schemas, and the validate-then-retry-once pipeline. Each provider-specific adapter (Tasks 12–16) only has to implement one method: `_call(messages, schema, image_bytes_by_label) -> raw_text`.

- [ ] **Step 1: Write tests**

`runner/tests/test_players.py`:

```python
from unittest.mock import MagicMock
import pytest
from dixit_ai.cards import Card
from dixit_ai.players.base import (
    LabeledHand, MoveError, _label_hand, _validate_story, _validate_pick,
    _validate_vote, StoryMove, PickMove, VoteMove, BaseAdapter,
)


def test_label_hand_deterministic_with_seed():
    hand = [Card(id=i) for i in [11, 22, 33, 44, 55, 66]]
    a = _label_hand(hand, seed=1)
    b = _label_hand(hand, seed=1)
    assert a.labels == b.labels
    assert set(a.labels.values()) == {c.id for c in hand}

def test_label_hand_uses_prefix():
    hand = [Card(id=i) for i in [11, 22, 33]]
    lh = _label_hand(hand, seed=0)
    assert list(lh.labels.keys()) == ["A", "B", "C"]


def test_validate_story_legal():
    lh = LabeledHand(labels={"A": 11, "B": 22, "C": 33}, ordered_labels=["A","B","C"])
    move = StoryMove(card="A", clue="x")
    card_id, clue = _validate_story(move, lh)
    assert card_id == 11
    assert clue == "x"

def test_validate_story_illegal_label():
    lh = LabeledHand(labels={"A": 11, "B": 22}, ordered_labels=["A","B"])
    move = StoryMove(card="C", clue="x")
    with pytest.raises(ValueError):
        _validate_story(move, lh)

def test_validate_vote_blocks_self():
    lh = LabeledHand(labels={"A": 11, "B": 22, "C": 33}, ordered_labels=["A","B","C"])
    move = VoteMove(card="B")
    with pytest.raises(ValueError):
        _validate_vote(move, lh, own_card_id=22)


class StubAdapter(BaseAdapter):
    model_id = "stub"
    display_name = "stub"
    org = "test"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = 0

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        self.calls += 1
        return self.responses.pop(0)


def test_adapter_retries_once_then_raises():
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['{"card": "ZZZ"}', '{"card": "BAD"}'])
    with pytest.raises(MoveError):
        a.pick_for_clue(hand, "x")
    assert a.calls == 2


def test_adapter_succeeds_on_second_try():
    hand = [Card(id=11), Card(id=22)]
    a = StubAdapter(responses=['not json', '{"card": "A"}'])
    chosen = a.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
    assert a.calls == 2
```

- [ ] **Step 2: Run tests — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py -v
```

- [ ] **Step 3: Extend `players/base.py`**

Replace `runner/dixit_ai/players/base.py` with:

```python
"""Player protocol + Pydantic move schemas + the validate/retry pipeline."""

from __future__ import annotations

import json
import random
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from dixit_ai.cards import Card, CardId, card_image_path


class MoveError(Exception):
    """Raised when a player fails to produce a valid move after retry."""


class Player(Protocol):
    model_id: str
    display_name: str
    org: str

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]: ...
    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId: ...
    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId: ...


# ----- Pydantic move schemas (adapter-internal) -----

class StoryMove(BaseModel):
    card: str
    clue: str = Field(min_length=1, max_length=140)


class PickMove(BaseModel):
    card: str


class VoteMove(BaseModel):
    card: str
    reasoning: str | None = Field(default=None, max_length=200)


# ----- Labeling -----

@dataclass
class LabeledHand:
    labels: dict[str, CardId]            # label → card id
    ordered_labels: list[str]            # the labels in their listed order

    @property
    def label_to_id(self) -> dict[str, CardId]:
        return self.labels


_ALPHABET = list(string.ascii_uppercase)


def _label_hand(cards: list[Card], seed: int | str | None = None) -> LabeledHand:
    """Assign freshly shuffled labels A, B, C, ... to the offered cards."""
    cards_shuffled = list(cards)
    rng = random.Random(seed)
    rng.shuffle(cards_shuffled)
    labels = _ALPHABET[: len(cards_shuffled)]
    mapping = {L: c.id for L, c in zip(labels, cards_shuffled)}
    return LabeledHand(labels=mapping, ordered_labels=labels)


# ----- Validation -----

def _validate_story(move: StoryMove, lh: LabeledHand) -> tuple[CardId, str]:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered labels {lh.ordered_labels}"
        )
    return lh.labels[move.card], move.clue


def _validate_pick(move: PickMove, lh: LabeledHand) -> CardId:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered labels {lh.ordered_labels}"
        )
    return lh.labels[move.card]


def _validate_vote(move: VoteMove, lh: LabeledHand, own_card_id: CardId) -> CardId:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered face-up labels {lh.ordered_labels}"
        )
    chosen = lh.labels[move.card]
    if chosen == own_card_id:
        raise ValueError(
            f"label {move.card!r} corresponds to your own card; you may not vote for it"
        )
    return chosen


# ----- BaseAdapter -----

@dataclass
class CallRecord:
    """Audit trail entry. One per SDK call."""
    turn: int | None
    phase: str
    model: str
    card_labels: dict[str, CardId]
    prompt: str
    response_raw: str
    parsed: dict | None
    attempts: int
    error: str | None = None


class BaseAdapter(ABC):
    model_id: str = "base"
    display_name: str = "base"
    org: str = "base"

    def __init__(self) -> None:
        self.audit: list[CallRecord] = []
        self._current_turn: int | None = None

    def set_turn(self, turn: int) -> None:
        self._current_turn = turn

    # Each concrete adapter implements _call.
    @abstractmethod
    def _call(
        self,
        *,
        messages: list[dict],
        schema: dict,
        image_bytes_by_label: dict[str, bytes],
    ) -> str:
        """Make one SDK call. Return the raw response text."""

    # ----- Public Player methods -----

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]:
        lh = _label_hand(hand)
        from dixit_ai.prompts import SYSTEM_PRELUDE, storyteller_user
        return self._run(
            phase="storytell",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, storyteller_user(lh.ordered_labels), lh
            ),
            schema=_schema_for_labels(lh.ordered_labels, with_clue=True),
            validator=lambda m: _validate_story(StoryMove(**m), lh),
        )

    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId:
        lh = _label_hand(hand)
        from dixit_ai.prompts import SYSTEM_PRELUDE, picker_user
        return self._run(
            phase="pick",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, picker_user(lh.ordered_labels, clue), lh
            ),
            schema=_schema_for_labels(lh.ordered_labels, with_clue=False),
            validator=lambda m: _validate_pick(PickMove(**m), lh),
        )

    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId:
        lh = _label_hand(face_up_cards)
        own_label = next(L for L, cid in lh.labels.items() if cid == own_card_id)
        from dixit_ai.prompts import SYSTEM_PRELUDE, voter_user
        return self._run(
            phase="vote",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, voter_user(lh.ordered_labels, clue, own_label), lh
            ),
            schema=_schema_for_vote(lh.ordered_labels, own_label),
            validator=lambda m: _validate_vote(VoteMove(**m), lh, own_card_id),
        )

    # ----- Internals -----

    def _build_messages(self, system: str, user: str, lh: LabeledHand) -> list[dict]:
        """A provider-neutral message shape. Adapters reshape this as needed."""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _run(self, *, phase, lh, messages, schema, validator):
        image_bytes_by_label: dict[str, bytes] = {}
        for label, cid in lh.labels.items():
            image_bytes_by_label[label] = card_image_path(cid).read_bytes()

        last_error: str | None = None
        last_raw = ""
        last_parsed: dict | None = None

        for attempt in (1, 2):
            try:
                raw = self._call(
                    messages=messages,
                    schema=schema,
                    image_bytes_by_label=image_bytes_by_label,
                )
                last_raw = raw
            except Exception as exc:
                last_error = f"sdk error: {exc}"
                self._record(phase, lh, "<sdk error>", "", None, attempt, last_error)
                # Try a retry by re-issuing same prompt; no need to add a fake assistant turn.
                continue

            try:
                parsed = _loose_parse(raw)
                last_parsed = parsed
            except Exception as exc:
                last_error = f"json parse: {exc}"
                self._record(phase, lh, messages_text(messages), raw, None, attempt, last_error)
                messages = _append_retry_turn(messages, raw, last_error)
                continue

            try:
                result = validator(parsed)
            except (ValidationError, ValueError) as exc:
                last_error = f"validation: {exc}"
                self._record(phase, lh, messages_text(messages), raw, parsed, attempt, last_error)
                messages = _append_retry_turn(messages, raw, last_error)
                continue

            self._record(phase, lh, messages_text(messages), raw, parsed, attempt, None)
            return result

        raise MoveError(f"{self.model_id} {phase} failed after 2 attempts: {last_error}")

    def _record(self, phase, lh, prompt, raw, parsed, attempts, error):
        self.audit.append(
            CallRecord(
                turn=self._current_turn,
                phase=phase,
                model=self.model_id,
                card_labels=dict(lh.labels),
                prompt=prompt,
                response_raw=raw,
                parsed=parsed,
                attempts=attempts,
                error=error,
            )
        )


# ----- Helpers -----

def _schema_for_labels(labels: list[str], *, with_clue: bool) -> dict:
    if with_clue:
        return {
            "type": "object",
            "properties": {
                "card": {"type": "string", "enum": labels},
                "clue": {"type": "string", "maxLength": 140, "minLength": 1},
            },
            "required": ["card", "clue"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {"card": {"type": "string", "enum": labels}},
        "required": ["card"],
        "additionalProperties": False,
    }


def _schema_for_vote(labels: list[str], own_label: str) -> dict:
    allowed = [L for L in labels if L != own_label]
    return {
        "type": "object",
        "properties": {
            "card": {"type": "string", "enum": allowed},
            "reasoning": {"type": "string", "maxLength": 200},
        },
        "required": ["card"],
        "additionalProperties": False,
    }


def _loose_parse(raw: str) -> dict:
    raw = raw.strip()
    # Strip ```json fences if present.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`")
    return json.loads(raw)


def messages_text(messages: list[dict]) -> str:
    return json.dumps(messages, default=str)


def _append_retry_turn(messages: list[dict], raw: str, error: str) -> list[dict]:
    return messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                f"Your response was rejected: {error}. "
                f"Respond again with valid JSON that matches the schema exactly."
            ),
        },
    ]
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/base.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add adapter base: labeling, validation, retry-once

BaseAdapter handles the parts shared by all five LLM adapters: assign
fresh A/B/C labels per call, Pydantic-validate the response, do one
retry with the validator's error fed back as an assistant+user turn,
and raise MoveError on second failure. Concrete adapters only implement
_call(messages, schema, image_bytes_by_label) -> raw_text.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Claude (Anthropic) adapter

**Files:**
- Create: `runner/dixit_ai/players/claude.py`
- Modify: `runner/tests/test_players.py`

- [ ] **Step 1: Write a contract test using a mocked SDK**

Append to `runner/tests/test_players.py`:

```python
from unittest.mock import MagicMock
from dixit_ai.players.claude import ClaudePlayer

def test_claude_adapter_returns_card_id_on_valid_response(monkeypatch):
    hand = [Card(id=11), Card(id=22)]

    # Build a fake anthropic.Messages response with a tool_use block.
    fake_tool_use = MagicMock(type="tool_use", name="submit_move", input={"card": "A"})
    fake_msg = MagicMock(content=[fake_tool_use], stop_reason="tool_use")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    player = ClaudePlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "soft wind")
    assert chosen in {11, 22}
    fake_client.messages.create.assert_called_once()
```

- [ ] **Step 2: Run — expect import failure**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_claude_adapter_returns_card_id_on_valid_response -v
```

- [ ] **Step 3: Implement Claude adapter**

`runner/dixit_ai/players/claude.py`:

```python
"""Anthropic Claude adapter via tool use."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from dixit_ai.players.base import BaseAdapter

MODEL = "claude-opus-4-7"


class ClaudePlayer(BaseAdapter):
    model_id = MODEL
    display_name = "Claude Opus 4.7"
    org = "Anthropic"

    def __init__(self, client: Any = None) -> None:
        super().__init__()
        if client is None:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.client = client

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs: list[dict] = []

        # Build the first user message: text + every card image.
        first_user_text = next(m["content"] for m in messages if m["role"] == "user")
        content_blocks: list[dict] = [{"type": "text", "text": first_user_text}]
        for label, blob in image_bytes_by_label.items():
            content_blocks.append({"type": "text", "text": f"Card {label}:"})
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(blob).decode(),
                    },
                }
            )
        user_msgs.append({"role": "user", "content": content_blocks})

        # Append any retry turns (assistant + user pairs).
        for m in messages:
            if m["role"] == "assistant":
                user_msgs.append({"role": "assistant", "content": m["content"]})
            elif m["role"] == "user" and m["content"] != first_user_text:
                user_msgs.append({"role": "user", "content": m["content"]})

        tool = {
            "name": "submit_move",
            "description": "Submit your move.",
            "input_schema": schema,
        }

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_move"},
            messages=user_msgs,
        )

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        # Fallback: return raw text if no tool block.
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return "{}"
```

- [ ] **Step 4: Run the test**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_claude_adapter_returns_card_id_on_valid_response -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/claude.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add Claude (Anthropic) adapter via tool use

Uses tool_choice={type:tool, name:submit_move} so the response is
schema-guaranteed JSON. Card images are sent as base64 image blocks
alongside the text prompt. Client is injectable for tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: GPT (OpenAI) adapter

**Files:**
- Create: `runner/dixit_ai/players/openai.py`
- Modify: `runner/tests/test_players.py`

- [ ] **Step 1: Write contract test**

Append to `runner/tests/test_players.py`:

```python
from dixit_ai.players.openai import OpenAIPlayer

def test_openai_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = OpenAIPlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
```

- [ ] **Step 2: Implement OpenAI adapter**

`runner/dixit_ai/players/openai.py`:

```python
"""OpenAI GPT adapter via structured outputs (JSON Schema, strict)."""

from __future__ import annotations

import base64
import os
from typing import Any

from dixit_ai.players.base import BaseAdapter

MODEL = "gpt-5"


class OpenAIPlayer(BaseAdapter):
    model_id = MODEL
    display_name = "GPT-5"
    org = "OpenAI"

    def __init__(self, client: Any = None, *, model: str = MODEL) -> None:
        super().__init__()
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.client = client
        self._model = model

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        # Build content array with text + images.
        content_parts: list[dict] = [{"type": "text", "text": first_user}]
        for label, blob in image_bytes_by_label.items():
            b64 = base64.b64encode(blob).decode()
            content_parts.append({"type": "text", "text": f"Card {label}:"})
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )

        oa_messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]
        # Append retry turns.
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "user" and m["content"] == first_user:
                continue
            oa_messages.append(m)

        resp = self.client.chat.completions.create(
            model=self._model,
            messages=oa_messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "submit_move",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        return resp.choices[0].message.content or "{}"
```

- [ ] **Step 3: Run test**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_openai_adapter_returns_card_id_on_valid_response -v
```

Expected: `1 passed`.

- [ ] **Step 4: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/openai.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add OpenAI GPT adapter via strict json_schema

Uses response_format={type:json_schema, strict:true} so the SDK rejects
non-conforming output before our Pydantic layer ever sees it. Card
images are inlined as data: URLs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Gemini (Google) adapter

**Files:**
- Create: `runner/dixit_ai/players/gemini.py`
- Modify: `runner/tests/test_players.py`

- [ ] **Step 1: Contract test**

Append to `runner/tests/test_players.py`:

```python
from dixit_ai.players.gemini import GeminiPlayer

def test_gemini_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]
    fake_resp = MagicMock(text='{"card": "A"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_resp

    player = GeminiPlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
```

- [ ] **Step 2: Implement Gemini adapter**

`runner/dixit_ai/players/gemini.py`:

```python
"""Google Gemini adapter via response_schema."""

from __future__ import annotations

import os
from typing import Any

from dixit_ai.players.base import BaseAdapter

MODEL = "gemini-2.5-pro"


class GeminiPlayer(BaseAdapter):
    model_id = MODEL
    display_name = "Gemini 2.5 Pro"
    org = "Google"

    def __init__(self, client: Any = None) -> None:
        super().__init__()
        if client is None:
            from google import genai
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.client = client

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        from google.genai.types import Part, GenerateContentConfig

        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        parts: list[Any] = [Part.from_text(text=first_user)]
        for label, blob in image_bytes_by_label.items():
            parts.append(Part.from_text(text=f"Card {label}:"))
            parts.append(Part.from_bytes(data=blob, mime_type="image/jpeg"))

        # Append retry turns as additional text parts.
        for m in messages:
            if m["role"] == "system" or m["content"] == first_user:
                continue
            parts.append(Part.from_text(text=f"[{m['role']}] {m['content']}"))

        config = GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        )

        resp = self.client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=config,
        )
        return resp.text or "{}"
```

- [ ] **Step 3: Run test**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_gemini_adapter_returns_card_id_on_valid_response -v
```

Expected: `1 passed`. (If the test fails because `Part.from_text` is mocked differently than expected, adjust the test to patch the import; the production code paths should still work when the real SDK is installed.)

If the Part import fails in the test (because `from google.genai.types import Part` may not be available under a pure MagicMock), patch it:

```python
def test_gemini_adapter_returns_card_id_on_valid_response(monkeypatch):
    fake_part = MagicMock()
    fake_part.from_text = lambda text: ("text", text)
    fake_part.from_bytes = lambda data, mime_type: ("bytes", len(data))
    fake_types = MagicMock(Part=fake_part, GenerateContentConfig=lambda **k: k)
    monkeypatch.setitem(__import__("sys").modules, "google.genai.types", fake_types)

    hand = [Card(id=11), Card(id=22)]
    fake_resp = MagicMock(text='{"card": "A"}')
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_resp

    player = GeminiPlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
```

- [ ] **Step 4: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/gemini.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add Google Gemini adapter via response_schema

Uses response_mime_type=application/json plus response_schema so the
SDK enforces our JSON schema. Card images are sent as Part.from_bytes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Grok (xAI) adapter

**Files:**
- Create: `runner/dixit_ai/players/grok.py`
- Modify: `runner/tests/test_players.py`

xAI is OpenAI-compatible — Grok adapter subclasses `OpenAIPlayer` with a different base URL and model name.

- [ ] **Step 1: Contract test**

Append to `runner/tests/test_players.py`:

```python
from dixit_ai.players.grok import GrokPlayer

def test_grok_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    player = GrokPlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
```

- [ ] **Step 2: Implement Grok adapter**

`runner/dixit_ai/players/grok.py`:

```python
"""xAI Grok adapter — OpenAI-compatible, different base URL."""

from __future__ import annotations

import os
from typing import Any

from dixit_ai.players.openai import OpenAIPlayer

MODEL = "grok-4"
BASE_URL = "https://api.x.ai/v1"


class GrokPlayer(OpenAIPlayer):
    model_id = MODEL
    display_name = "Grok 4"
    org = "xAI"

    def __init__(self, client: Any = None) -> None:
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=BASE_URL)
        super().__init__(client=client, model=MODEL)
```

- [ ] **Step 3: Run test**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_grok_adapter_returns_card_id_on_valid_response -v
```

Expected: `1 passed`.

- [ ] **Step 4: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/grok.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add xAI Grok adapter as OpenAIPlayer subclass

Same OpenAI SDK, base_url pointed at api.x.ai. Inherits the
json_schema / strict pipeline from OpenAIPlayer; xAI's structured
output support is best-effort, so the Pydantic validation in the base
adapter is the real guardrail.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Pixtral (Mistral) adapter

**Files:**
- Create: `runner/dixit_ai/players/pixtral.py`
- Modify: `runner/tests/test_players.py`

- [ ] **Step 1: Contract test**

```python
from dixit_ai.players.pixtral import PixtralPlayer

def test_pixtral_adapter_returns_card_id_on_valid_response():
    hand = [Card(id=11), Card(id=22)]
    fake_choice = MagicMock(message=MagicMock(content='{"card": "A"}'))
    fake_resp = MagicMock(choices=[fake_choice])
    fake_client = MagicMock()
    fake_client.chat.complete.return_value = fake_resp

    player = PixtralPlayer(client=fake_client)
    chosen = player.pick_for_clue(hand, "x")
    assert chosen in {11, 22}
```

- [ ] **Step 2: Implement Pixtral adapter**

`runner/dixit_ai/players/pixtral.py`:

```python
"""Mistral Pixtral Large adapter via response_format=json_object."""

from __future__ import annotations

import base64
import os
from typing import Any

from dixit_ai.players.base import BaseAdapter

MODEL = "pixtral-large-latest"


class PixtralPlayer(BaseAdapter):
    model_id = "pixtral-large"
    display_name = "Pixtral Large"
    org = "Mistral"

    def __init__(self, client: Any = None) -> None:
        super().__init__()
        if client is None:
            from mistralai import Mistral
            client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.client = client

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        # Pixtral takes content as a list of mixed text+image parts.
        content_parts: list[dict] = [{"type": "text", "text": first_user}]
        for label, blob in image_bytes_by_label.items():
            b64 = base64.b64encode(blob).decode()
            content_parts.append({"type": "text", "text": f"Card {label}:"})
            content_parts.append(
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64}"}
            )

        # Mistral's response_format=json_object doesn't enforce a schema; we tell the
        # model what the schema is in the prompt itself and rely on Pydantic to validate.
        schema_hint = (
            "\n\nYour response MUST be valid JSON matching this schema:\n"
            f"{schema}"
        )
        content_parts[0]["text"] = first_user + schema_hint

        ms_messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]
        for m in messages:
            if m["role"] == "system" or m["content"] == first_user:
                continue
            ms_messages.append(m)

        resp = self.client.chat.complete(
            model=MODEL,
            messages=ms_messages,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"
```

- [ ] **Step 3: Run test**

```bash
cd /home/matthijs/git/dixit/runner && python -m pytest tests/test_players.py::test_pixtral_adapter_returns_card_id_on_valid_response -v
```

Expected: `1 passed`.

- [ ] **Step 4: Register the lineup**

`runner/dixit_ai/players/__init__.py`:

```python
"""The fixed lineup of five players for the nightly game."""

from __future__ import annotations

from dixit_ai.players.claude import ClaudePlayer
from dixit_ai.players.openai import OpenAIPlayer
from dixit_ai.players.gemini import GeminiPlayer
from dixit_ai.players.grok import GrokPlayer
from dixit_ai.players.pixtral import PixtralPlayer


def default_lineup():
    """Instantiate the five flagship players. Reads API keys from env."""
    return [
        ClaudePlayer(),
        OpenAIPlayer(),
        GeminiPlayer(),
        GrokPlayer(),
        PixtralPlayer(),
    ]
```

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/players/pixtral.py runner/dixit_ai/players/__init__.py runner/tests/test_players.py
git commit -m "$(cat <<'EOF'
Add Mistral Pixtral adapter and register full lineup

Pixtral has response_format=json_object (valid JSON guaranteed, schema
NOT enforced), so the adapter embeds the schema in the prompt and
relies on the BaseAdapter Pydantic check + retry. players/__init__.py
exposes default_lineup() for the runner.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Runner orchestration + Amsterdam-hour guard

**Files:**
- Create: `runner/dixit_ai/runner.py`
- Create: `runner/dixit_ai/__main__.py`

- [ ] **Step 1: Implement the runner**

`runner/dixit_ai/runner.py`:

```python
"""Top-level orchestration: load state, play a game, write results."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dixit_ai.engine import play_game, GameResult
from dixit_ai.elo import update_ratings
from dixit_ai.players import default_lineup
from dixit_ai.players.base import BaseAdapter
from dixit_ai.storage import (
    DATA_DIR, load_elo, save_elo, append_index, save_game, game_exists,
)


AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def _today_in_amsterdam() -> str:
    return datetime.now(AMSTERDAM).date().isoformat()


def _is_amsterdam_midnight() -> bool:
    return datetime.now(AMSTERDAM).hour == 0


def _placements_from_scores(scores: dict[str, int], elo: dict[str, dict]) -> list[str]:
    def key(model_id):
        return (-scores[model_id], -elo["models"][model_id]["rating"])
    return sorted(scores, key=key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the midnight Amsterdam check.")
    parser.add_argument("--mock-players", action="store_true",
                        help="Use RandomPlayers instead of real LLMs.")
    parser.add_argument("--date", default=None,
                        help="Override the game_id date (YYYY-MM-DD).")
    args = parser.parse_args(argv)

    if not args.dry_run and not _is_amsterdam_midnight():
        print(f"Not midnight in Amsterdam ({datetime.now(AMSTERDAM).isoformat()}); skipping.")
        return 0

    game_id = args.date or _today_in_amsterdam()
    if game_exists(game_id):
        print(f"Game {game_id} already exists; refusing to overwrite.")
        return 0

    if args.mock_players:
        from dixit_ai.players.random_player import RandomPlayer
        players = [
            RandomPlayer(model_id="claude-opus-4-7", display_name="Claude Opus 4.7", org="Anthropic"),
            RandomPlayer(model_id="gpt-5", display_name="GPT-5", org="OpenAI"),
            RandomPlayer(model_id="gemini-2.5-pro", display_name="Gemini 2.5 Pro", org="Google"),
            RandomPlayer(model_id="grok-4", display_name="Grok 4", org="xAI"),
            RandomPlayer(model_id="pixtral-large", display_name="Pixtral Large", org="Mistral"),
        ]
    else:
        players = default_lineup()

    elo = load_elo()
    started = datetime.now(tz=AMSTERDAM).isoformat()

    try:
        result: GameResult = play_game(players, rng_seed=game_id)
    except Exception:
        # Catastrophic failure: write an error doc, still commit.
        ended = datetime.now(tz=AMSTERDAM).isoformat()
        err_path = DATA_DIR / "games" / f"{game_id}.error.json"
        err_path.write_text(json.dumps({
            "game_id": game_id,
            "started_at": started,
            "ended_at": ended,
            "traceback": traceback.format_exc(),
        }, indent=2))
        append_index({
            "game_id": game_id, "date": game_id, "status": "errored",
            "winner": None, "turns": 0,
            "final_scores": {}, "elo_deltas": {},
        })
        return 2

    ended = datetime.now(tz=AMSTERDAM).isoformat()

    # Update Elo.
    placements = _placements_from_scores(result.final_scores, elo)
    current_ratings = {m: elo["models"][m]["rating"] for m in result.final_scores}
    new_ratings = update_ratings(current_ratings, placements)
    elo_before = dict(current_ratings)
    elo_after = {m: round(new_ratings[m], 2) for m in new_ratings}

    for m, new_r in elo_after.items():
        elo["models"][m]["rating"] = new_r
        elo["models"][m]["games"] += 1
        if m == result.winner:
            elo["models"][m]["wins"] += 1
    elo["updated_at"] = ended

    # Build game doc.
    game_doc = {
        "game_id": game_id,
        "status": result.status,
        "started_at": started,
        "ended_at": ended,
        "seed": game_id,
        "players": [p.model_id for p in players],
        "turns": [dataclasses.asdict(t) for t in result.turns],
        "final_scores": result.final_scores,
        "elo_before": elo_before,
        "elo_after": elo_after,
    }

    # Raw audit trail: collect from each player.
    raw_lines: list[dict] = []
    for p in players:
        if isinstance(p, BaseAdapter):
            for c in p.audit:
                raw_lines.append(dataclasses.asdict(c))

    save_game(game_id=game_id, game_doc=game_doc, raw_lines=raw_lines)
    save_elo(elo)
    append_index({
        "game_id": game_id,
        "date": game_id,
        "status": result.status,
        "winner": result.winner,
        "turns": len(result.turns),
        "final_scores": result.final_scores,
        "elo_deltas": {m: round(elo_after[m] - elo_before[m], 2) for m in elo_after},
    })
    print(f"game {game_id} written: winner={result.winner}, turns={len(result.turns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`runner/dixit_ai/__main__.py`:

```python
from dixit_ai.runner import main
import sys
sys.exit(main())
```

- [ ] **Step 2: Smoke test with mock players**

Delete any stale game file first (the runner refuses to overwrite):

```bash
cd /home/matthijs/git/dixit
rm -f data/games/2099-01-01.json data/games/2099-01-01.raw.jsonl
cd runner && python -m dixit_ai --dry-run --mock-players --date 2099-01-01
```

Expected output: `game 2099-01-01 written: winner=..., turns=...`

Then verify the files:

```bash
ls /home/matthijs/git/dixit/data/games/
cat /home/matthijs/git/dixit/data/index.json | python -m json.tool | head -20
```

Expected: `2099-01-01.json` and `2099-01-01.raw.jsonl` exist; `index.json` has one row.

- [ ] **Step 3: Roll back the smoke test artifacts**

Mock-game artifacts should NOT be committed. Roll them back:

```bash
cd /home/matthijs/git/dixit
rm -f data/games/2099-01-01.json data/games/2099-01-01.raw.jsonl
# Reset elo.json and index.json to pristine state.
git checkout -- data/elo.json data/index.json
```

Verify clean:

```bash
git status data/ 
```

Expected: no changes in `data/`.

- [ ] **Step 4: Commit the runner**

```bash
cd /home/matthijs/git/dixit
git add runner/dixit_ai/runner.py runner/dixit_ai/__main__.py
git commit -m "$(cat <<'EOF'
Add runner orchestration with Amsterdam-midnight guard

main() loads elo.json, plays a game, applies Elo updates, writes
game JSON + raw audit jsonl, appends to index. Skips when it's not
midnight in Europe/Amsterdam unless --dry-run is passed. --mock-players
uses RandomPlayers (no API calls) for smoke testing. On catastrophic
failure writes an .error.json doc and an errored row to index.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Astro site scaffolding + leaderboard page

**Files:**
- Create: `web/package.json`
- Create: `web/astro.config.mjs`
- Create: `web/tsconfig.json`
- Create: `web/src/lib/data.ts`
- Create: `web/src/pages/index.astro`
- Create: `web/src/components/EloTable.astro`

- [ ] **Step 1: Scaffold the package**

`web/package.json`:

```json
{
  "name": "dixit-web",
  "type": "module",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "check": "astro check"
  },
  "dependencies": {
    "astro": "^4.16.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@astrojs/check": "^0.9.0"
  }
}
```

`web/astro.config.mjs`:

```js
import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'directory' },
});
```

`web/tsconfig.json`:

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": ["src/**/*", ".astro/types.d.ts"]
}
```

- [ ] **Step 2: Build the data loader**

`web/src/lib/data.ts`:

```typescript
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(here, '../../../data');

export interface ModelElo {
  display_name: string;
  org: string;
  rating: number;
  games: number;
  wins: number;
}

export interface EloDoc {
  updated_at: string;
  models: Record<string, ModelElo>;
}

export interface IndexRow {
  game_id: string;
  date: string;
  status: 'complete' | 'errored' | 'turn_limit';
  winner: string | null;
  turns: number;
  final_scores: Record<string, number>;
  elo_deltas: Record<string, number>;
}

export interface TurnRecord {
  turn: number;
  storyteller: string;
  clue: string | null;
  storyteller_card: number | null;
  submissions: Record<string, number>;
  face_up_order: number[];
  votes: Record<string, number>;
  scores_delta: Record<string, number>;
  scores_total: Record<string, number>;
  degraded: string[];
}

export interface GameDoc {
  game_id: string;
  status: string;
  started_at: string;
  ended_at: string;
  seed: string;
  players: string[];
  turns: TurnRecord[];
  final_scores: Record<string, number>;
  elo_before: Record<string, number>;
  elo_after: Record<string, number>;
}

export function loadElo(): EloDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'elo.json'), 'utf-8'));
}

export function loadIndex(): IndexRow[] {
  return JSON.parse(readFileSync(resolve(dataDir, 'index.json'), 'utf-8'));
}

export function loadGame(gameId: string): GameDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'games', `${gameId}.json`), 'utf-8'));
}
```

- [ ] **Step 3: Leaderboard component**

`web/src/components/EloTable.astro`:

```astro
---
import { loadElo, type EloDoc } from '../lib/data';
const elo: EloDoc = loadElo();
const rows = Object.entries(elo.models)
  .map(([id, m]) => ({ id, ...m }))
  .sort((a, b) => b.rating - a.rating);
---
<table>
  <thead>
    <tr><th>#</th><th>Model</th><th>Org</th><th>Elo</th><th>Games</th><th>Wins</th></tr>
  </thead>
  <tbody>
    {rows.map((r, i) => (
      <tr>
        <td class="rank">{i + 1}</td>
        <td>{r.display_name}</td>
        <td class="muted">{r.org}</td>
        <td class="num">{Math.round(r.rating)}</td>
        <td class="num">{r.games}</td>
        <td class="num">{r.wins}</td>
      </tr>
    ))}
  </tbody>
</table>

<style>
table { width: 100%; border-collapse: collapse; font: 13px/1.4 ui-monospace, Menlo, monospace; }
th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #1d2128; }
th { color: #7a8290; font-weight: 400; letter-spacing: .12em; text-transform: uppercase; font-size: 11px; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.rank { color: #7a8290; }
.muted { color: #7a8290; }
</style>
```

- [ ] **Step 4: Index page**

`web/src/pages/index.astro`:

```astro
---
import EloTable from '../components/EloTable.astro';
import { loadIndex, loadElo } from '../lib/data';

const games = loadIndex().slice().reverse().slice(0, 30);
const elo = loadElo();
---
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Dixit</title>
  <style is:global>
    :root {
      --bg: #0f1115; --fg: #e6e8ee; --muted: #7a8290; --pos: #6fcf97; --neg: #eb5757;
    }
    html, body { background: var(--bg); color: var(--fg); margin: 0; padding: 0;
                 font: 14px/1.5 ui-monospace, Menlo, monospace; }
    main { max-width: 760px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
    .subtitle { color: var(--muted); font-size: 12px; letter-spacing: .18em;
                text-transform: uppercase; }
    section { margin-top: 32px; }
    a { color: var(--fg); }
  </style>
</head>
<body>
  <main>
    <p class="subtitle">AI Dixit · updated {elo.updated_at}</p>
    <h1>Leaderboard</h1>
    <section><EloTable /></section>

    <section>
      <h2 class="subtitle">Recent games</h2>
      <ul style="list-style:none; padding:0; font: 13px/1.6 ui-monospace, Menlo, monospace;">
        {games.map(g => (
          <li>
            <a href={`/games/${g.game_id}`}>{g.date}</a>
            <span style="color:var(--muted)"> · winner </span>
            {g.winner ?? <em style="color:var(--muted)">none</em>}
            <span style="color:var(--muted)"> · {g.turns} turns</span>
            {g.status !== 'complete' && (
              <span style="color:var(--neg)"> · {g.status}</span>
            )}
          </li>
        ))}
        {games.length === 0 && <li class="muted">No games yet.</li>}
      </ul>
    </section>
  </main>
</body>
</html>
```

- [ ] **Step 5: Install and build**

```bash
cd /home/matthijs/git/dixit/web
npm install
npm run build
```

Expected: `dist/` directory created; build succeeds. `dist/index.html` exists.

If `npm install` is slow or unavailable in the test environment, skip the build and continue — the workflow on GitHub will run it.

- [ ] **Step 6: Commit**

```bash
cd /home/matthijs/git/dixit
git add web/package.json web/astro.config.mjs web/tsconfig.json web/src/
git commit -m "$(cat <<'EOF'
Scaffold Astro site + leaderboard page

Static Astro site reads data/*.json at build time via web/src/lib/data.ts.
Index page renders the Elo leaderboard (sorted desc by rating) and the
30 most recent games linking to /games/<id>. Monospaced dashboard style.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Per-game log page

**Files:**
- Create: `web/src/pages/games/[id].astro`
- Create: `web/src/components/TurnRow.astro`
- Create: `web/src/components/CardImage.astro`

- [ ] **Step 1: Card thumbnail**

`web/src/components/CardImage.astro`:

```astro
---
interface Props { cardId: number; size?: number; }
const { cardId, size = 80 } = Astro.props;
const padded = String(cardId).padStart(5, '0');
const src = `/cards/card_${padded}.jpg`;
---
<img src={src} alt={`Card ${cardId}`} width={size} height={size}
     style="border-radius:6px; object-fit:cover; display:inline-block; margin-right:4px;" />
```

- [ ] **Step 2: Turn row**

`web/src/components/TurnRow.astro`:

```astro
---
import CardImage from './CardImage.astro';
import type { TurnRecord } from '../lib/data';

interface Props { turn: TurnRecord; players: string[]; }
const { turn, players } = Astro.props;

const isSkipped = turn.clue === null;
const correctVoters = Object.entries(turn.votes)
  .filter(([, cid]) => cid === turn.storyteller_card)
  .map(([v]) => v);
---
<article>
  <header>
    <span class="turn-no">turn {turn.turn + 1}</span>
    <span class="storyteller"><strong>{turn.storyteller}</strong></span>
    {isSkipped ? (
      <span class="skipped">— forfeited</span>
    ) : (
      <span class="clue">"{turn.clue}"</span>
    )}
  </header>

  {!isSkipped && (
    <div class="cards">
      {turn.face_up_order.map(cid => {
        const owner = Object.entries(turn.submissions).find(([, c]) => c === cid)?.[0];
        const votes = Object.entries(turn.votes).filter(([, c]) => c === cid).map(([v]) => v);
        const isStoryteller = cid === turn.storyteller_card;
        return (
          <div class="card" data-storyteller={isStoryteller}>
            <CardImage cardId={cid} />
            <div class="meta">
              <div class="owner">{owner}</div>
              {votes.length > 0 && <div class="votes">votes: {votes.join(', ')}</div>}
              {isStoryteller && <div class="badge">STORYTELLER</div>}
            </div>
          </div>
        );
      })}
    </div>
  )}

  <div class="scores">
    {players.map(p => {
      const delta = turn.scores_delta[p] ?? 0;
      return (
        <span class="score">
          {p}: <strong>{turn.scores_total[p] ?? 0}</strong>
          {delta !== 0 && (
            <span class={delta > 0 ? 'pos' : 'neg'}> {delta > 0 ? '+' : ''}{delta}</span>
          )}
        </span>
      );
    })}
  </div>

  {turn.degraded.length > 0 && (
    <div class="degraded">⚠ {turn.degraded.join(', ')}</div>
  )}
</article>

<style>
article { border-bottom: 1px solid #1d2128; padding: 14px 0; }
header { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
.turn-no { color: var(--muted); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; }
.clue { color: #f0d680; font-style: italic; }
.skipped { color: var(--muted); }
.cards { display: flex; gap: 10px; margin: 10px 0; flex-wrap: wrap; }
.card { display: flex; gap: 6px; align-items: flex-start; }
.card[data-storyteller='true'] { background: rgba(255,255,255,0.04); border-radius: 8px; padding: 4px; }
.meta { font-size: 11px; line-height: 1.4; }
.owner { color: var(--fg); }
.votes { color: var(--muted); }
.badge { color: #f0d680; font-weight: 600; letter-spacing: .12em; font-size: 10px; }
.scores { display: flex; gap: 12px; font-size: 12px; flex-wrap: wrap; margin-top: 4px; }
.pos { color: var(--pos); }
.neg { color: var(--neg); }
.degraded { color: var(--neg); font-size: 12px; margin-top: 6px; }
</style>
```

- [ ] **Step 3: Dynamic route**

`web/src/pages/games/[id].astro`:

```astro
---
import TurnRow from '../../components/TurnRow.astro';
import { loadGame, loadIndex } from '../../lib/data';

export function getStaticPaths() {
  const rows = loadIndex();
  return rows.map(r => ({ params: { id: r.game_id } }));
}

const { id } = Astro.params as { id: string };
const game = loadGame(id);
const winner = Object.entries(game.final_scores)
  .sort((a, b) => b[1] - a[1])[0]?.[0];
---
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AI Dixit · {id}</title>
  <style is:global>
    :root { --bg: #0f1115; --fg: #e6e8ee; --muted: #7a8290; --pos: #6fcf97; --neg: #eb5757; }
    html, body { background: var(--bg); color: var(--fg); margin: 0; padding: 0;
                 font: 14px/1.5 ui-monospace, Menlo, monospace; }
    main { max-width: 900px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
    .subtitle { color: var(--muted); font-size: 12px; letter-spacing: .18em;
                text-transform: uppercase; }
    a { color: var(--fg); }
  </style>
</head>
<body>
  <main>
    <p class="subtitle"><a href="/">← leaderboard</a> · game {id}</p>
    <h1>{id} · winner: {winner}</h1>
    <p class="subtitle">status: {game.status} · {game.turns.length} turns</p>

    <section>
      {game.turns.map(t => <TurnRow turn={t} players={game.players} />)}
    </section>
  </main>
</body>
</html>
```

- [ ] **Step 4: Build to confirm**

```bash
cd /home/matthijs/git/dixit/web && npm run build
```

Expected: build succeeds. If `data/index.json` is `[]`, the dynamic route generates zero pages — that's fine.

- [ ] **Step 5: Commit**

```bash
cd /home/matthijs/git/dixit
git add web/src/pages/games/ web/src/components/TurnRow.astro web/src/components/CardImage.astro
git commit -m "$(cat <<'EOF'
Add per-game log page rendering turns, cards, votes, and forfeits

games/[id].astro is a dynamic static route — getStaticPaths reads
data/index.json so a page is emitted per committed game. Each TurnRow
shows the clue, the face-up cards with owners and vote tallies (the
storyteller's card highlighted), the running totals, and any
'<model>:<phase>:forfeit' markers from the degraded list.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 20: GitHub Actions — nightly runner

**Files:**
- Create: `.github/workflows/nightly.yml`

- [ ] **Step 1: Workflow**

`.github/workflows/nightly.yml`:

```yaml
name: nightly-game

on:
  schedule:
    - cron: "0 22 * * *"
    - cron: "0 23 * * *"
  workflow_dispatch: {}

jobs:
  play:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install runner
        working-directory: runner
        run: pip install -e .

      - name: Play a game
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY:    ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY:    ${{ secrets.GEMINI_API_KEY }}
          XAI_API_KEY:       ${{ secrets.XAI_API_KEY }}
          MISTRAL_API_KEY:   ${{ secrets.MISTRAL_API_KEY }}
        run: python -m dixit_ai

      - name: Commit results
        run: |
          git config user.name  "dixit-bot"
          git config user.email "dixit-bot@users.noreply.github.com"
          if git diff --quiet -- data/; then
            echo "no data changes; the Amsterdam-hour guard probably skipped this run"
            exit 0
          fi
          git add data/
          git commit -m "game $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: Commit**

```bash
cd /home/matthijs/git/dixit
git add .github/workflows/nightly.yml
git commit -m "$(cat <<'EOF'
Add nightly GitHub Actions workflow

Two cron entries (22:00 UTC, 23:00 UTC) so one fires at NL midnight
year-round. The Python guard inside runner.main() exits early on the
wrong one. Commits data/*.json back to main; the push triggers
deploy.yml to rebuild the site.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 21: GitHub Actions — site deploy

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Workflow**

`.github/workflows/deploy.yml`:

```yaml
name: deploy

on:
  push:
    branches: [main]
    paths:
      - "data/**"
      - "web/**"
      - ".github/workflows/deploy.yml"
  workflow_dispatch: {}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deploy.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: web/package-lock.json

      - name: Install
        working-directory: web
        run: npm ci

      - name: Build
        working-directory: web
        run: npm run build

      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist

      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Generate package-lock.json so `npm ci` works in CI**

```bash
cd /home/matthijs/git/dixit/web && npm install
```

This creates `package-lock.json` (already created by Task 18 step 5; if not, this re-creates it).

- [ ] **Step 3: Commit**

```bash
cd /home/matthijs/git/dixit
git add .github/workflows/deploy.yml web/package-lock.json
git commit -m "$(cat <<'EOF'
Add Pages deploy workflow

Fires on push to main whenever data/, web/, or this file changes.
Uses npm ci against web/package-lock.json for reproducible builds.
Publishes the static dist/ via actions/deploy-pages.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 22: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

`README.md`:

````markdown
# AI Dixit

Five vision-capable LLMs from different orgs play one full Dixit game per night.
Results are committed to this repo as JSON, and a static site renders the
leaderboard + per-game log.

- **Spec:** [`docs/superpowers/specs/2026-05-22-ai-dixit-design.md`](docs/superpowers/specs/2026-05-22-ai-dixit-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md`](docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md)

## Lineup

Anthropic (Claude Opus 4.7) · OpenAI (GPT-5) · Google (Gemini 2.5 Pro) ·
xAI (Grok 4) · Mistral (Pixtral Large).

## Structure

- `runner/` — Python game engine + five LLM adapters. Runs nightly in GH Actions.
- `web/` — Astro static site, rebuilt every time `data/` changes.
- `data/` — `elo.json`, `index.json`, and one `games/<date>.json` per game.

## Local development

Runner:

```bash
cd runner
pip install -e ".[dev]"
python -m pytest -v
python -m dixit_ai --dry-run --mock-players --date 2099-01-01
```

Site:

```bash
cd web
npm install
npm run dev          # http://localhost:4321
npm run build
```

## CI

- `.github/workflows/nightly.yml` — schedule 22:00 + 23:00 UTC daily; the runner
  exits early on the cron that's not midnight in Europe/Amsterdam.
- `.github/workflows/deploy.yml` — on every push that touches `data/` or `web/`,
  build Astro and publish to GitHub Pages.

Set repo secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
`XAI_API_KEY`, `MISTRAL_API_KEY`.

## Re-running a day

The runner refuses to overwrite an existing `data/games/<date>.json`. To redo
a day:

```bash
rm data/games/<date>.json data/games/<date>.raw.jsonl
git checkout HEAD~1 -- data/elo.json data/index.json   # roll back state
# then either wait for cron or workflow_dispatch the nightly job
```
````

- [ ] **Step 2: Commit**

```bash
cd /home/matthijs/git/dixit
git add README.md
git commit -m "$(cat <<'EOF'
Add README pointing to spec, plan, and local dev commands

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review summary

**Spec coverage:**
- Goals (nightly game, Elo, static site, all state in repo) → Tasks 17, 7, 18–19, 8–9.
- Game rules (deck, scoring, forfeits, end-of-game, reshuffle) → Tasks 3, 4, 5, 6.
- Architecture (engine + adapters, separated halves) → file map enforces it; engine.py has no SDK imports.
- Player protocol → Task 5 (initial) + Task 11 (full base).
- Structured output (per-provider) → Tasks 12–16, one task each.
- Forfeit rules → Tasks 5 and 6 lock semantics.
- Elo (K=32 placement-based, frozen pairs) → Task 7.
- Data schemas (`elo.json`, `index.json`, `games/<date>.json`, `<date>.raw.jsonl`) → Tasks 8, 9, 17.
- Scheduling (two crons + AMS guard) → Tasks 17 + 20.
- Deployment → Tasks 20, 21.
- Testing strategy (engine + Elo + adapter contract) → Tasks 4, 5, 6, 7, 11–16.
- Operations (re-running, adding a model) → README in Task 22.
- Risk notes (card copyright, model drift, clue quality) → already in spec.

**Identifier consistency:** `play_game`, `score_turn`, `update_ratings`, `load_elo`, `save_elo`, `append_index`, `save_game`, `game_exists`, `default_lineup` — all referenced names are defined in earlier tasks.

**No placeholders:** every step has executable code or commands.
