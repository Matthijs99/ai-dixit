"""Placement-based pairwise Elo updates (K=32)."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Sequence

K = 32.0
INITIAL_RATING = 1500.0

log = logging.getLogger(__name__)


def ensure_model_entries(elo: dict, players: Iterable[Any]) -> None:
    """Make sure every player has an entry in elo["models"].

    For a player whose model_id isn't present, carry over the rating, games,
    and wins from the first matching `previous_ids` entry that *is* present.
    Otherwise initialize fresh at INITIAL_RATING. Mutates `elo` in place; the
    original previous_ids entry is kept (as a retired record) so historical
    games keep resolving.

    Finally, reconcile every entry against the active roster: entries whose
    model_id is in the roster have any `retired` flag cleared; all others are
    tagged `retired: True` so the leaderboard can hide them while their
    history stays available for past games.
    """
    players = list(players)
    models = elo.setdefault("models", {})
    for p in players:
        if p.model_id in models:
            continue
        prior = next(
            (pid for pid in getattr(p, "previous_ids", []) if pid in models),
            None,
        )
        if prior is not None:
            src = models[prior]
            log.info(
                "elo: %s inheriting from %s (rating=%.2f, games=%d, wins=%d)",
                p.model_id, prior, src["rating"], src["games"], src["wins"],
            )
            models[p.model_id] = {
                "display_name": p.display_name,
                "org": p.org,
                "rating": src["rating"],
                "games": src["games"],
                "wins": src["wins"],
            }
        else:
            log.info("elo: initializing %s at %.0f", p.model_id, INITIAL_RATING)
            models[p.model_id] = {
                "display_name": p.display_name,
                "org": p.org,
                "rating": INITIAL_RATING,
                "games": 0,
                "wins": 0,
            }

    active_ids = {p.model_id for p in players}
    for model_id, entry in models.items():
        if model_id in active_ids:
            entry.pop("retired", None)
        else:
            entry["retired"] = True


def expected_score(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected-score formula."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


def update_ratings(
    ratings: Mapping[str, float],
    placements: Sequence[str],
    *,
    scores: Mapping[str, int] | None = None,
) -> dict[str, float]:
    """Apply pairwise Elo updates over all pairs.

    `placements` is the ordering from 1st place to last. `scores`, if
    provided, is the final score map; pairs with equal scores are treated
    as draws (result 0.5/0.5). If `scores` is omitted, placement order
    decides the pairwise result (1 for the earlier-placed player).
    Per-pair updates use the pre-game ratings (frozen) so update order
    doesn't affect the result. The input is not mutated.
    """
    new = {m: float(r) for m, r in ratings.items()}
    base = dict(new)  # snapshot of pre-game ratings
    n = len(placements)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = placements[i], placements[j]
            if scores is not None and scores.get(a, 0) == scores.get(b, 0):
                result_a = 0.5
            else:
                result_a = 1.0
            e_a = expected_score(base[a], base[b])
            new[a] += K * (result_a - e_a)
            new[b] += K * ((1 - result_a) - (1 - e_a))
    return new
