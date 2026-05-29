"""Per-model standings: games, wins and total points.

Models are ranked by points-per-game — the average final Dixit score across the
games a model has played. Each model_id counts only its own games; a superseded
model keeps its own tally and moves to the retired section rather than handing
anything down to its successor.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

log = logging.getLogger(__name__)


# Some entries are the same underlying model under different ids (e.g. the same
# Claude version run with and without extended thinking) and should share one
# leaderboard line. Map alias id -> canonical id; everything keys off canonical.
MODEL_ALIASES: dict[str, str] = {
    "claude-opus-4-7-thinking": "claude-opus-4-7",
}


def canonical_id(model_id: str) -> str:
    return MODEL_ALIASES.get(model_id, model_id)


# ----- Roster bookkeeping -----

def _new_entry(player: Any) -> dict:
    return {
        "display_name": player.display_name,
        "org": player.org,
        "games": 0,
        "wins": 0,
        "points": 0,
    }


def _reconcile_retired(models: dict, active_ids: set[str]) -> None:
    """Tag entries not in the active roster `retired`; clear the flag otherwise."""
    for model_id, entry in models.items():
        if model_id in active_ids:
            entry.pop("retired", None)
        else:
            entry["retired"] = True


def ensure_model_entries(stats: dict, players: Iterable[Any]) -> None:
    """Make sure every player has an entry in stats["models"].

    New players start fresh (games/wins/points at 0). Entries absent from the
    active roster are flagged `retired` and kept, so their history stays visible
    in the retired section. Mutates `stats` in place.
    """
    players = list(players)
    models = stats.setdefault("models", {})
    for p in players:
        mid = canonical_id(p.model_id)
        if mid not in models:
            log.info("stats: initializing %s", mid)
            models[mid] = _new_entry(p)
    _reconcile_retired(models, {canonical_id(p.model_id) for p in players})


# ----- Recording results -----

def record_game(
    models: dict,
    scores: Mapping[str, int],
    winner: str | None,
) -> None:
    """Fold one game's final scores into the standings.

    For each model in `scores`, increment its game count, add its final score to
    its running points total, and credit a win if it is `winner`. Entries must
    already exist (call `ensure_model_entries` first). Mutates `models` in place.
    """
    winner_id = canonical_id(winner) if winner is not None else None
    for model_id, score in scores.items():
        entry = models[canonical_id(model_id)]
        entry["games"] += 1
        entry["points"] += score
        if canonical_id(model_id) == winner_id:
            entry["wins"] += 1
