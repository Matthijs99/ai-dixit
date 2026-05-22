# AI Dixit

Five vision-capable LLMs from different orgs play one full Dixit game per night.
Results are committed to this repo as JSON, and a static site renders the
leaderboard + per-game log.

- **Spec:** [`docs/superpowers/specs/2026-05-22-ai-dixit-design.md`](docs/superpowers/specs/2026-05-22-ai-dixit-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md`](docs/superpowers/plans/2026-05-22-ai-dixit-implementation.md)

## Lineup

Anthropic (Claude Opus 4.7) · OpenAI (GPT-5.5) · Google (Gemini 2.5 Pro) ·
xAI (Grok 4.3) · Mistral (Mistral Medium 3.5).

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
