"""Top-level orchestration: load state, play a game, write results."""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from dixit_ai.engine import GameResult, play_game
from dixit_ai.players.base import BaseAdapter
from dixit_ai.stats import ensure_model_entries, record_game
from dixit_ai.storage import (
    DATA_DIR,
    append_index,
    game_exists,
    load_index,
    load_stats,
    save_game,
    save_stats,
)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")

log = logging.getLogger(__name__)


def _today_in_amsterdam() -> str:
    return datetime.now(AMSTERDAM).date().isoformat()


def _is_amsterdam_midnight() -> bool:
    return datetime.now(AMSTERDAM).hour == 0


def _now_iso_seconds() -> str:
    """Amsterdam time, second precision — no microseconds in committed JSON."""
    return datetime.now(tz=AMSTERDAM).replace(microsecond=0).isoformat()


@dataclasses.dataclass
class _ReplayPlayer:
    """Minimal player stand-in for replaying historical games."""
    model_id: str
    display_name: str
    org: str


def recompute_stats() -> int:
    """Rebuild data/stats.json from scratch by replaying index.json.

    Metadata (display_name, org) is read from the existing stats.json — notably
    for retired models, whose names live only there and not in models.yaml. The
    active-roster retired flags come from models.yaml. Re-run this after changing
    how standings are computed.
    """
    from dixit_ai.players import load_roster

    old = _read_json_or_empty(DATA_DIR / "stats.json")
    meta = {
        mid: (e["display_name"], e["org"])
        for mid, e in old.get("models", {}).items()
    }
    roster = load_roster()
    active = [e["model_id"] for e in roster]

    def player(mid: str) -> _ReplayPlayer:
        name, org = meta.get(mid, (mid, "?"))
        return _ReplayPlayer(mid, name, org)

    index = load_index()
    stats: dict = {"models": {}}
    games_replayed = 0
    for row in index:
        scores = row.get("final_scores") or {}
        if row.get("status") != "complete" or not scores:
            continue
        ensure_model_entries(stats, [player(mid) for mid in scores])
        record_game(stats["models"], scores, row.get("winner"))
        games_replayed += 1

    # Reconcile retired flags against the current roster.
    ensure_model_entries(stats, [player(mid) for mid in active])
    stats["updated_at"] = old.get("updated_at") or _now_iso_seconds()
    save_stats(stats)
    print(f"recomputed stats.json from {games_replayed} games")
    return 0


def _read_json_or_empty(path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


def run_smoke() -> int:
    """Verify every model is callable: one storytell per model.

    Writes nothing. Returns non-zero if any model fails, so CI goes red. Each
    model gets its own try/except, so one failure can't hide the others.
    """
    import random

    from dixit_ai.cards import Deck
    from dixit_ai.engine import HAND_SIZE
    from dixit_ai.players import base, default_lineup

    # Fail fast: a bad model id should error in seconds, not ~9 min of backoff.
    base.MAX_ATTEMPTS = 3
    base.SDK_ERROR_BACKOFF_SECONDS = 5.0

    players = default_lineup()
    deck = Deck(rng=random.Random("smoke"))

    results = []
    for p in players:
        hand = deck.deal(HAND_SIZE)
        try:
            _, clue = p.storytell(hand)
            results.append((True, p, f"clue={clue!r}"))
        except Exception as exc:
            results.append((False, p, f"{type(exc).__name__}: {exc}"))

    log.info("===== smoke report =====")
    for ok, p, note in results:
        log.info("  %-4s %-22s %-32s %s", "PASS" if ok else "FAIL",
                 p.display_name, p.model_id, note)

    failed = [p.model_id for ok, p, _ in results if not ok]
    if failed:
        log.error("smoke FAILED: %d/%d models unreachable: %s",
                  len(failed), len(results), ", ".join(failed))
        return 1
    log.info("smoke OK: all %d models callable", len(results))
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the midnight Amsterdam check.",
    )
    parser.add_argument(
        "--mock-players",
        action="store_true",
        help="Use RandomPlayers instead of real LLMs.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Override the game_id date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Verify every model is callable (one move each), write nothing.",
    )
    parser.add_argument(
        "--recompute-stats",
        action="store_true",
        help="Rebuild stats.json from index.json, then exit.",
    )
    args = parser.parse_args(argv)

    if args.smoke:
        return run_smoke()

    if args.recompute_stats:
        return recompute_stats()

    if not args.dry_run and not _is_amsterdam_midnight():
        print(
            f"Not midnight in Amsterdam ({datetime.now(AMSTERDAM).isoformat()}); skipping."
        )
        return 0

    game_id = args.date or _today_in_amsterdam()
    if game_exists(game_id):
        print(f"Game {game_id} already exists; refusing to overwrite.")
        return 0

    if args.mock_players:
        from dixit_ai.players import load_roster
        from dixit_ai.players.random_player import RandomPlayer

        # Adapter name → org. Keep this small map in sync with players/__init__.py.
        _ORGS = {
            "claude": "Anthropic",
            "openai": "OpenAI",
            "gemini": "Google",
            "grok": "xAI",
            "mistral": "Mistral",
            "bytedance": "Bytedance",
            "moonshot": "Moonshot",
        }
        players = []
        for entry in load_roster():
            player = RandomPlayer(
                model_id=entry["model_id"],
                display_name=entry["display_name"],
                org=_ORGS.get(entry["adapter"], "random"),
            )
            players.append(player)
    else:
        from dixit_ai.players import default_lineup

        players = default_lineup()

    stats = load_stats()
    ensure_model_entries(stats, players)
    started = _now_iso_seconds()

    try:
        result: GameResult = play_game(players, rng_seed=game_id)
    except Exception:
        # Catastrophic failure: write an error doc, still commit.
        ended = _now_iso_seconds()
        err_path = DATA_DIR / "games" / f"{game_id}.error.json"
        err_path.write_text(
            json.dumps(
                {
                    "game_id": game_id,
                    "started_at": started,
                    "ended_at": ended,
                    "traceback": traceback.format_exc(),
                },
                indent=2,
            )
        )
        append_index(
            {
                "game_id": game_id,
                "date": game_id,
                "status": "errored",
                "winner": None,
                "turns": 0,
                "final_scores": {},
            }
        )
        return 2

    ended = _now_iso_seconds()

    # Fold this game's final scores into the standings.
    record_game(stats["models"], result.final_scores, result.winner)
    stats["updated_at"] = ended

    # Build game doc.
    game_doc = {
        "game_id": game_id,
        "status": result.status,
        "started_at": started,
        "ended_at": ended,
        "seed": game_id,
        "players": result.play_order,
        "turns": [dataclasses.asdict(t) for t in result.turns],
        "final_scores": result.final_scores,
    }

    # Raw audit trail: collect from each player.
    raw_lines: list[dict] = []
    for p in players:
        if isinstance(p, BaseAdapter):
            for c in p.audit:
                raw_lines.append(dataclasses.asdict(c))

    save_game(game_id=game_id, game_doc=game_doc, raw_lines=raw_lines)
    save_stats(stats)
    append_index(
        {
            "game_id": game_id,
            "date": game_id,
            "status": result.status,
            "winner": result.winner,
            "turns": len(result.turns),
            "final_scores": result.final_scores,
        }
    )
    print(
        f"game {game_id} written: winner={result.winner}, turns={len(result.turns)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
