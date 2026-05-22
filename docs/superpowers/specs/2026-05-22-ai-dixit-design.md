# AI Dixit — design

A web app where five vision-capable LLMs from different organizations play one full
game of Dixit every night. Results are committed to the repo as JSON, and a static
site renders a leaderboard (Elo) and a per-game log.

## Goals & non-goals

**Goals**

- Run one full Dixit game per night, unattended, at midnight Europe/Amsterdam.
- Maintain an Elo rating per model, updated after each game.
- Publish a public, read-only static site with a leaderboard and a per-game log.
- All game state is in the repo. No database, no backend, no auth.

**Non-goals**

- Humans playing alongside models. Models play models only.
- Interactive replay / animation. The site is a data dashboard.
- Per-model profile pages, Elo-over-time charts, or other deeper drilldowns.
  May be added later; not in this spec.
- Real-time updates. Nightly cadence is the contract.

## Players

Fixed lineup of five flagship vision-capable models, one per major org:

| model_id           | display_name      | org       | API           |
|--------------------|-------------------|-----------|---------------|
| `claude-opus-4-7`  | Claude Opus 4.7   | Anthropic | first-party   |
| `gpt-5`            | GPT-5             | OpenAI    | first-party   |
| `gemini-2.5-pro`   | Gemini 2.5 Pro    | Google    | first-party   |
| `grok-4`           | Grok 4            | xAI       | first-party   |
| `pixtral-large`    | Pixtral Large     | Mistral   | first-party   |

Adding a 6th model later is one new adapter file + one row in `data/elo.json`.
No schema changes needed.

## Game rules

Standard Dixit rules, implemented faithfully:

- Deck: 100 cards (the `cards/` directory from `jminuscula/dixit-online`,
  vendored into `web/public/cards/`).
- Each player starts with 6 cards.
- Turns rotate through the player list. Each turn:
  1. Storyteller looks at their hand, picks one card, writes a clue
     (a word, phrase, or sentence ≤140 chars).
  2. Every other player picks one card from their hand that matches the clue.
  3. All submitted cards (storyteller's + decoys) are shuffled face-up.
  4. Every non-storyteller who submitted a card votes for the card they think
     is the storyteller's. Players may not vote for their own card.
  5. Scoring (`P` = non-storytellers who participated in this turn, i.e.
     submitted a card AND voted; forfeiters are excluded from the denominator):
     - If **all** or **none** of `P` voted for the storyteller's card:
       storyteller gets **0**, every member of `P` gets **2**.
     - Otherwise: storyteller and the correct voters in `P` get **3** each.
     - Every non-storyteller who submitted a card gets **+1** for each vote
       their decoy received, capped at **+3**. (A player who forfeited the
       pick has no card on the table and gets no decoy bonus.)
  6. Each player whose hand is below 6 draws 1 card. If the draw deck is
     empty (or has fewer cards than needed for the round of draws), shuffle the
     discard pile back into the deck first. The 100 cards thus cycle
     indefinitely — the deck is never truly exhausted while play continues.
- End condition: game ends at the start of any turn where any player has
  **≥30 points**. Winner is the highest-scoring player; ties broken by current
  Elo (higher wins).
- Hard cap: 50 turns. If hit, game ends with `status: "turn_limit"` and the
  highest-scoring player at that point is declared the winner.

## Architecture

Two physically separated halves of the repo that meet only through committed JSON.

```
┌────────────────────────────────────────────────────────────┐
│  GitHub Actions cron (twice/day in UTC; one is real)       │
│                                                            │
│   python -m dixit_ai.runner                                │
│   ┌──────────┐    ┌──────────────────┐                     │
│   │  Engine  │◄───┤  Player adapters │                     │
│   │ (pure    │    │  one per model   │                     │
│   │  rules)  │───►│                  │                     │
│   └──────────┘    └──────────────────┘                     │
│         │                                                  │
│         ▼                                                  │
│   data/games/<date>.json                                   │
│   data/games/<date>.raw.jsonl                              │
│   data/elo.json (rewritten in place)                       │
│   data/index.json (one row appended)                       │
│   git commit + push                                        │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼ (push triggers deploy.yml)
┌────────────────────────────────────────────────────────────┐
│  GitHub Pages (Astro static site)                          │
│                                                            │
│   pages/index.astro       ← leaderboard                    │
│   pages/games/[id].astro  ← per-game log                   │
│                                                            │
│   reads data/*.json at build time; site rebuilds whenever  │
│   the runner pushes new data                               │
└────────────────────────────────────────────────────────────┘
```

Key invariants:

- The engine has zero LLM SDK imports.
- The site has zero Python deps and no runtime data fetching.
- The only contract between the two halves is the JSON schema in `data/`.

## Repo structure

```
ai-dixit/
├── runner/
│   ├── dixit_ai/
│   │   ├── engine.py            # pure rules; no SDK imports
│   │   ├── deck.py              # card metadata + RNG-seeded shuffle
│   │   ├── elo.py               # placement-based pairwise updates
│   │   ├── players/
│   │   │   ├── base.py          # Player protocol + ParsedMove + validation
│   │   │   ├── random_player.py # tests only; not used at runtime
│   │   │   ├── claude.py
│   │   │   ├── openai.py
│   │   │   ├── gemini.py
│   │   │   ├── grok.py          # OpenAI-compatible client, x.ai base_url
│   │   │   └── pixtral.py
│   │   ├── prompts.py           # all prompt templates in one place
│   │   ├── runner.py            # entry point: __main__
│   │   └── storage.py           # reads/writes data/*.json
│   ├── tests/
│   │   ├── test_engine.py
│   │   ├── test_elo.py
│   │   └── test_players.py
│   └── pyproject.toml
│
├── web/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.astro
│   │   │   └── games/[id].astro
│   │   ├── components/
│   │   │   ├── EloTable.astro
│   │   │   ├── TurnRow.astro
│   │   │   └── CardImage.astro
│   │   └── lib/data.ts
│   ├── public/cards/            # 100 vendored .jpg files
│   ├── astro.config.mjs
│   └── package.json
│
├── data/
│   ├── elo.json
│   ├── index.json
│   └── games/
│       ├── 2026-05-22.json
│       └── 2026-05-22.raw.jsonl
│
├── .github/workflows/
│   ├── nightly.yml
│   └── deploy.yml
│
└── README.md
```

## Player protocol

The linchpin of the design. The engine speaks in `CardId`s (the real integer
id of a card); the adapter handles labeling internally. Every adapter conforms
to:

```python
class Player(Protocol):
    model_id: str       # "claude-opus-4-7"
    display_name: str   # "Claude Opus 4.7"
    org: str            # "Anthropic"

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]: ...
        # returns: (chosen card id from hand, clue text)

    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId: ...
        # returns: chosen card id from hand

    def vote(self, face_up_cards: list[Card], clue: str,
             own_card_id: CardId) -> CardId: ...
        # returns: chosen card id from face_up_cards (never own_card_id)
```

Each adapter is a thin wrapper (~40–60 lines) that:

1. Assigns fresh labels to the offered cards (`A`, `B`, …) and builds a prompt.
2. Calls one SDK.
3. Parses the JSON response into an adapter-internal Pydantic move model.
4. Validates legality and maps the label back to a `CardId`.
5. Either returns the `CardId` (or `(CardId, clue)` for storytell) or raises
   `MoveError` (after one retry — see Structured output below).

### Card labels in prompts

Cards are presented to models as **labeled images**, not raw filenames or
integer ids:

```
"Card A:" <image>
"Card B:" <image>
"Card C:" <image>
... etc
```

Labels (`A`, `B`, `C`, …) are freshly shuffled and assigned per call. The model
chooses a label; the adapter maps label → real card id internally. This:

- Prevents leakage (filenames don't reach the model).
- Closes the output space (the model can't hallucinate a card id that doesn't
  exist in this prompt's offering).
- Keeps prompts uniform across providers.

## Structured output

Three of five providers can guarantee schema-conformant JSON; the other two
require Pydantic validation on our side. All adapters end up at the same shape
via the same validation layer.

### Move schemas (Pydantic, adapter-internal)

These are used only inside the adapter, for SDK response parsing. The engine
never sees them. The hand size can shrink below 6 once the deck is depleted,
so `card` is plain `str` and the adapter validates membership against the
labels offered in this specific prompt:

```python
class StoryMove(BaseModel):
    card: str   # must be one of the offered hand labels for this call
    clue: constr(min_length=1, max_length=140)

class PickMove(BaseModel):
    card: str   # must be one of the offered hand labels for this call

class VoteMove(BaseModel):
    card: str   # must be one of the offered face-up labels for this call
    reasoning: constr(max_length=200) | None = None
```

The set of valid labels is therefore prompt-specific. For providers that
accept a JSON schema (Anthropic/OpenAI/Gemini), the adapter builds the schema
fresh per call with the concrete `enum` of labels offered, so the SDK itself
rejects out-of-set values before they reach our Pydantic layer.

### Per-provider mechanism

| Provider           | Mechanism                                                      | Schema-guaranteed? |
|--------------------|----------------------------------------------------------------|--------------------|
| Anthropic (Claude) | Tool use + `tool_choice: {type:"tool", name:"submit_move"}`    | Yes                |
| OpenAI (GPT-5)     | `response_format: {type:"json_schema", strict:true}`           | Yes                |
| Google (Gemini)    | `response_mime_type:"application/json"` + `response_schema`    | Yes                |
| xAI (Grok)         | OpenAI-compatible Structured Outputs (same SDK, diff base_url) | Best-effort        |
| Mistral (Pixtral)  | `response_format: {type:"json_object"}` (valid JSON only)      | No                 |

### Validation pipeline (in `players/base.py`)

```
1. SDK call returns text/JSON.
2. Pydantic-parse into the move type. On failure → step 4.
3. Legality check:
     - storytell / pick: chosen label is in the offered hand
     - vote: chosen label is in the face-up set AND is not the player's own card
   On failure → step 4.
4. Retry once: append the previous response as an `assistant` message and a
   `user` message: "Your response was rejected: <error>. Respond again
   following the schema exactly."
5. On second failure → raise MoveError.
```

A model has 2 shots per move, with the validator's error fed back verbatim.

## Forfeit rules

When `MoveError` is raised, the engine records a forfeit. It does NOT substitute
a random move. Behavior per phase:

- **Storyteller forfeit** → entire turn is skipped. No clue, no submissions,
  no votes, no scoring. Next player becomes storyteller. Deck doesn't advance,
  hands don't change.
- **Pick forfeit** → that player sits out the whole turn. No card on the table
  (so no decoy votes can be earned) and no vote (so no storyteller bonus).
  Other players' turn proceeds normally, with N−1 face-up cards revealed.
- **Vote forfeit** → that player just doesn't vote. They earn no storyteller
  bonus. Their decoy card stays on the table and can still earn them +1 per
  vote from others.

Every forfeit is recorded as `"degraded": ["<model>:<phase>:forfeit"]` on the
turn record, so it's visible on the per-game page. A model that consistently
forfeits will tank in Elo — the right signal.

## Elo

Placement-based pairwise updates, K=32, standard Elo formula.

```
sort players by final score (desc), ties broken by current Elo (desc)
for each pair (i, j) with i finishing above j in the ranking:
    E_i = 1 / (1 + 10^((R_j - R_i)/400))
    R_i += 32 * (1 - E_i)
    R_j += 32 * (0 - (1 - E_i))
```

With 5 players that's 10 pairwise updates per game. Sweeping the field
(1st-of-5) typically gains ~+50; last place loses ~the same.

All models bootstrap at rating 1500 in `data/elo.json` at repo init.

## Data schemas

### `data/elo.json` — rewritten in place every game

```json
{
  "updated_at": "2026-05-22T03:14:00Z",
  "models": {
    "claude-opus-4-7":  {"display_name": "Claude Opus 4.7",  "org": "Anthropic", "rating": 1606, "games": 12, "wins": 4},
    "gpt-5":            {"display_name": "GPT-5",            "org": "OpenAI",    "rating": 1488, "games": 12, "wins": 2},
    "gemini-2.5-pro":   {"display_name": "Gemini 2.5 Pro",   "org": "Google",    "rating": 1612, "games": 12, "wins": 4},
    "grok-4":           {"display_name": "Grok 4",           "org": "xAI",       "rating": 1434, "games": 12, "wins": 1},
    "pixtral-large":    {"display_name": "Pixtral Large",    "org": "Mistral",   "rating": 1466, "games": 12, "wins": 1}
  }
}
```

### `data/index.json` — append-only

Lets the leaderboard show recent games without reading every game file.

```json
[
  {
    "game_id": "2026-05-22",
    "date": "2026-05-22",
    "status": "complete",
    "winner": "gemini-2.5-pro",
    "turns": 18,
    "final_scores": {"gemini-2.5-pro": 31, "claude-opus-4-7": 24, "gpt-5": 18, "pixtral-large": 14, "grok-4": 9},
    "elo_deltas":   {"gemini-2.5-pro": 18, "claude-opus-4-7": 6,  "gpt-5": 0,  "pixtral-large": -9, "grok-4": -15}
  }
]
```

`status` is one of `"complete"`, `"errored"`, `"turn_limit"`.

### `data/games/<date>.json` — one file per game

```json
{
  "game_id": "2026-05-22",
  "status": "complete",
  "started_at": "2026-05-22T03:00:11Z",
  "ended_at":   "2026-05-22T03:14:02Z",
  "seed": "2026-05-22",
  "players": ["claude-opus-4-7", "gpt-5", "gemini-2.5-pro", "grok-4", "pixtral-large"],
  "turns": [
    {
      "turn": 0,
      "storyteller": "claude-opus-4-7",
      "clue": "a whisper that became a road",
      "storyteller_card": 47,
      "submissions": {
        "claude-opus-4-7": 47,
        "gpt-5":           12,
        "gemini-2.5-pro":  88,
        "grok-4":          31,
        "pixtral-large":   60
      },
      "face_up_order": [88, 47, 12, 60, 31],
      "votes": {
        "gpt-5":          47,
        "gemini-2.5-pro": 88,
        "grok-4":         47,
        "pixtral-large":  12
      },
      "scores_delta": {"claude-opus-4-7": 3, "gpt-5": 3, "gemini-2.5-pro": 1, "grok-4": 3, "pixtral-large": 1},
      "scores_total": {"claude-opus-4-7": 3, "gpt-5": 3, "gemini-2.5-pro": 1, "grok-4": 3, "pixtral-large": 1},
      "degraded": []
    }
  ],
  "final_scores": {"...": "..."},
  "elo_before":   {"...": "..."},
  "elo_after":    {"...": "..."}
}
```

Notes:

- `storyteller_card` is duplicated in `submissions` for convenience.
- `face_up_order` is the shuffled reveal order shown to voters — preserved so
  the replay matches what the voting models actually saw.
- `degraded` lists tags like `"grok-4:vote:forfeit"`. Empty `[]` when clean.
- A player who forfeits their pick is **omitted** from `submissions` and
  `votes` (they sit out the whole turn).
- A non-storyteller who forfeits only their vote is in `submissions` but
  **omitted** from `votes`.
- If a turn is skipped due to storyteller forfeit, the turn record still
  exists; `clue` is `null`, `submissions`/`votes`/`face_up_order` are empty,
  `scores_delta` is all zeros, and `degraded` contains
  `"<model>:storytell:forfeit"`.

### `data/games/<date>.raw.jsonl` — audit trail, committed

One line per SDK call. Not consumed by the site; useful for debugging.

```jsonl
{"turn": 0, "phase": "storytell", "model": "claude-opus-4-7", "card_labels": {"A":47,"B":23,"C":15,"D":91,"E":4,"F":67}, "prompt": "...", "response_raw": "...", "parsed": {"card":"A","clue":"a whisper..."}, "attempts": 1, "latency_ms": 2143}
```

## Game loop

```
1. load_elo()
2. deck = shuffle(all_100_cards, seed=YYYY-MM-DD)   # deterministic per date
   discard = []
3. deal 6 cards to each of 5 players from deck
4. while turn_index < 50:
     if any player score ≥ 30:        break          # win condition
     storyteller = players[turn_index % 5]
     a. storyteller.storytell(hand)                  # → (card_id, clue) or MoveError → forfeit-turn, advance
     b. for every other player whose hand is non-empty:
          player.pick_for_clue(hand, clue)           # → card_id or MoveError → that player sits out
     c. shuffle submitted cards; reveal as face_up_order
     d. for every non-storyteller who submitted a card:
          player.vote(face_up, clue, own_card_id)    # → card_id or MoveError → no vote
     e. score_turn() per rules above
     f. move all played cards (storyteller_card + submitted decoys) → discard
     g. refill draws: for each player whose hand is below 6:
          if deck is empty:
              shuffle discard into deck; discard = []
          if deck is non-empty:
              draw 1 card from deck into hand
        (with 5 players × max 6 cards = 30 in hand, deck+discard ≥ 70, so
        every player always draws successfully)
     h. append TurnRecord to turns[]
     i. turn_index += 1
5. determine winner (highest final score; Elo tiebreak)
   set status = "complete" if any player ≥ 30 else "turn_limit"
6. update_elo(final_placements)
7. write data/games/<date>.json, data/games/<date>.raw.jsonl
   rewrite data/elo.json
   append to data/index.json
8. git commit -m "game <date>" && git push
```

## Error handling

Three failure categories:

**1. Transient API failure** — exponential backoff (2s, 6s, 18s), 3 attempts.
Most SDKs handle this internally; we let them and only wrap as a fallback.

**2. Malformed model output** — handled by the validation pipeline above:
2 attempts (one initial + one with error fed back), then `MoveError` → forfeit.

**3. Catastrophic failure** (engine bug, all 5 models down, network outage):

- Engine wraps the whole game in `try`/`except`.
- On unhandled exception:
  - Write `data/games/<date>.error.json` with traceback + partial state.
  - Do NOT modify `data/elo.json` (no half-applied updates).
  - Append a row to `data/index.json` with `"status": "errored"`.
  - Still commit and push, so the site reflects the failure visibly.
  - The GH Actions step exits non-zero so the workflow page shows red.

## Scheduling

GitHub Actions cron has no timezone support, and the Netherlands switches
between CET (UTC+1) and CEST (UTC+2). We handle this with two cron entries
and an Amsterdam-hour guard in the runner. Exactly one execution per day,
exactly at NL midnight, regardless of DST.

```yaml
schedule:
  - cron: "0 22 * * *"   # = NL midnight during CEST (summer)
  - cron: "0 23 * * *"   # = NL midnight during CET  (winter)
```

```python
from zoneinfo import ZoneInfo
from datetime import datetime
if datetime.now(ZoneInfo("Europe/Amsterdam")).hour != 0:
    return  # the other cron entry will fire at NL midnight
```

## Deployment

### `.github/workflows/nightly.yml`

```yaml
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
        with: { python-version: "3.12" }
      - run: pip install -e runner/
      - run: python -m dixit_ai.runner
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY:    ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY:    ${{ secrets.GEMINI_API_KEY }}
          XAI_API_KEY:       ${{ secrets.XAI_API_KEY }}
          MISTRAL_API_KEY:   ${{ secrets.MISTRAL_API_KEY }}
      - name: Commit results
        run: |
          git config user.name  "dixit-bot"
          git config user.email "dixit-bot@users.noreply.github.com"
          git add data/
          git commit -m "game $(date -u +%Y-%m-%d)" || echo "no changes"
          git push
```

### `.github/workflows/deploy.yml`

```yaml
on:
  push:
    branches: [main]
    paths: ["data/**", "web/**", ".github/workflows/deploy.yml"]
  workflow_dispatch: {}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions: { contents: read, pages: write, id-token: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - working-directory: web
        run: npm ci && npm run build
      - uses: actions/upload-pages-artifact@v3
        with: { path: web/dist }
      - uses: actions/deploy-pages@v4
```

### Secrets

Five repo-level secrets in GitHub → Settings → Secrets → Actions:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`,
`MISTRAL_API_KEY`. All first-party APIs; no third-party hosting providers.

## Testing

**Engine unit tests** (~20 tests, run on every PR)

- Scoring matrix: 0 votes / all votes / partial votes; decoy +1 bonus.
- Forfeit semantics: storyteller / pick / vote forfeit behaviors, including
  the "all-or-none" denominator excluding forfeiters.
- Win condition: ≥30 ends game; 50-turn cap → `turn_limit`; Elo tiebreak on
  equal scores.
- Determinism: same seed + same player decisions → same final state.
- Card cycling: hand always 6; discard reshuffles back into deck when needed;
  no card ever exists in two locations (hand/deck/discard) at once.

Engine tests use `RandomPlayer` only. Fast, fully deterministic.

**Elo unit tests** (~6 tests)

- Pairwise update math against hand-computed expected values.
- Conservation: sum of deltas across a game is ~0 (rounding ±1).
- Symmetry: identical-rating + identical-placement players get identical updates.

**Player adapter contract tests** (~5 tests, one per adapter, SDK mocked)

- Valid JSON response → correct `ParsedMove`.
- Bad JSON → adapter retries once with error fed back, then raises `MoveError`.
- Illegal move (self-vote, card-not-in-hand) → same retry+raise behavior.

No real API calls in CI. No frontend tests beyond `astro check`.

**Pre-launch smoke test**

`python -m dixit_ai.runner --dry-run --mock-players` plays a full game with
`RandomPlayer`s, writes a real JSON file, and `cd web && npm run build`
confirms the site builds. Documented in `runner/README.md`.

## Operations

- **First-run bootstrap**: hand-write `data/elo.json` with all five models at
  rating 1500, 0 games. Hand-write empty `data/index.json` as `[]`.
- **Re-running a day**: delete `data/games/<date>.json` and `<date>.raw.jsonl`,
  revert `data/elo.json` and `data/index.json` to previous state, then
  `workflow_dispatch` the nightly job. The runner refuses to overwrite an
  existing game file as a safety check.
- **Adding a 6th model**: implement the adapter, append a row to
  `data/elo.json` at rating 1500, append to the lineup constant in
  `dixit_ai/players/__init__.py`.
- **Failure notifications**: GH Actions default email-on-failure. The site
  also surfaces failures via `status: errored` rows in the index.
- **Cost monitoring**: external — each provider's dashboard usage alert at
  ~$20/month. Bounded internally by the 50-turn cap and 2-retry cap:
  `5 × 50 × 1.5 ≈ 375` model calls/game max.

## Risks & open notes

- **Card image copyright**. The 100 cards from `jminuscula/dixit-online` are
  reproductions of Marie Cardouat's copyrighted art for Libellud. Vendoring
  them for a personal/portfolio site is consistent with how the referenced
  repo distributes them, but this would be a real problem if the site ever
  went commercial or large-scale. Out of scope for this design; flagged here.
- **Model availability drift**. The five named flagships (Opus 4.7, GPT-5,
  Gemini 2.5 Pro, Grok 4, Pixtral Large) are correct at design time; if any
  is deprecated or renamed, the adapter constant gets bumped, no schema
  change.
- **Clue quality**. Real Dixit relies on subtle, evocative clues. LLMs may
  produce dull or over-literal clues, which would compress the score
  distribution and make Elo less discriminating. We accept this; it's part
  of the experiment.
