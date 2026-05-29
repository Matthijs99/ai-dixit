# AI Dixit

Six vision-capable LLMs from different orgs play one full Dixit game per night.
Results are committed to this repo as JSON, and a static site renders the
leaderboard + per-game log.

- **Spec:** [`docs/superpowers/specs/2026-05-22-ai-dixit-design.md`](docs/superpowers/specs/2026-05-22-ai-dixit-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md`](docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md)

## Lineup

The top 6 distinct orgs on the LMArena vision leaderboard (excluding rows tagged
"preliminary"), each on its best eligible model — snapshot 2026-05-26:

Anthropic (Claude Opus 4.7, thinking) · Google (Gemini 3.1 Pro) · OpenAI (GPT-5.5) ·
xAI (Grok 4.20 reasoning) · ByteDance (Seed 2.0 Pro) · Moonshot (Kimi K2.6).

If a model is unavailable it simply forfeits its moves and the game still
finishes; there is no automatic backup. The `smoke-test` workflow checks that
every model is callable — run it (Actions → smoke-test) after editing the roster.

## Structure

- `runner/` — Python game engine + six LLM adapters. Runs nightly in GH Actions.
- `web/` — Astro static site, rebuilt every time `data/` changes.
- `data/` — `stats.json`, `index.json`, and one `games/<date>.json` per game.

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

- `.github/workflows/nightly.yml` — schedule 22:00 + 23:00 UTC every day; the
  runner exits early on the cron that's not midnight in Europe/Amsterdam.
- `.github/workflows/deploy.yml` — on every push that touches `data/` or `web/`,
  build Astro and publish to GitHub Pages.

Set repo secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`,
`XAI_API_KEY`, `MOONSHOT_API_KEY`, and `BYTEPLUS_API_KEY` (BytePlus ModelArk,
used for the ByteDance Seed model).

## Re-running a day

The runner refuses to overwrite an existing `data/games/<date>.json`. To redo
a day:

```bash
rm data/games/<date>.json data/games/<date>.raw.jsonl
git checkout HEAD~1 -- data/stats.json data/index.json   # roll back state
# then either wait for cron or workflow_dispatch the nightly job
```
