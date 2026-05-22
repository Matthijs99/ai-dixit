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
