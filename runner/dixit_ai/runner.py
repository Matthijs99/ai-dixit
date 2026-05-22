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

from dixit_ai.elo import update_ratings
from dixit_ai.engine import GameResult, play_game
from dixit_ai.players.base import BaseAdapter
from dixit_ai.storage import (
    DATA_DIR,
    append_index,
    game_exists,
    load_elo,
    save_elo,
    save_game,
)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


def _today_in_amsterdam() -> str:
    return datetime.now(AMSTERDAM).date().isoformat()


def _is_amsterdam_midnight() -> bool:
    return datetime.now(AMSTERDAM).hour == 0


def _placements_from_scores(
    scores: dict[str, int], elo: dict[str, dict]
) -> list[str]:
    def key(model_id: str) -> tuple[int, float]:
        return (-scores[model_id], -elo["models"][model_id]["rating"])

    return sorted(scores, key=key)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )


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
    args = parser.parse_args(argv)

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
        from dixit_ai.players.random_player import RandomPlayer

        players = [
            RandomPlayer(
                model_id="claude-opus-4-7",
                display_name="Claude Opus 4.7",
                org="Anthropic",
            ),
            RandomPlayer(
                model_id="gpt-5.5", display_name="GPT-5.5", org="OpenAI"
            ),
            RandomPlayer(
                model_id="gemini-2.5-pro",
                display_name="Gemini 2.5 Pro",
                org="Google",
            ),
            RandomPlayer(
                model_id="grok-4.3", display_name="Grok 4.3", org="xAI"
            ),
            RandomPlayer(
                model_id="mistral-medium-3.5",
                display_name="Mistral Medium 3.5",
                org="Mistral",
            ),
        ]
    else:
        from dixit_ai.players import default_lineup

        players = default_lineup()

    elo = load_elo()
    started = datetime.now(tz=AMSTERDAM).isoformat()

    try:
        result: GameResult = play_game(players, rng_seed=game_id)
    except Exception:
        # Catastrophic failure: write an error doc, still commit.
        ended = datetime.now(tz=AMSTERDAM).isoformat()
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
                "elo_deltas": {},
            }
        )
        return 2

    ended = datetime.now(tz=AMSTERDAM).isoformat()

    # Update Elo.
    placements = _placements_from_scores(result.final_scores, elo)
    current_ratings = {
        m: elo["models"][m]["rating"] for m in result.final_scores
    }
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
    append_index(
        {
            "game_id": game_id,
            "date": game_id,
            "status": result.status,
            "winner": result.winner,
            "turns": len(result.turns),
            "final_scores": result.final_scores,
            "elo_deltas": {
                m: round(elo_after[m] - elo_before[m], 2) for m in elo_after
            },
        }
    )
    print(
        f"game {game_id} written: winner={result.winner}, turns={len(result.turns)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
