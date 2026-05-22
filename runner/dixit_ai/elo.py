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
    Per-pair updates use the pre-game ratings (frozen), so update order
    doesn't affect the result.
    Returns a new dict with updated ratings; the input is not mutated.
    """
    new = {m: float(r) for m, r in ratings.items()}
    base = dict(new)   # snapshot of pre-game ratings
    n = len(placements)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = placements[i], placements[j]
            e_a = expected_score(base[a], base[b])
            new[a] += K * (1 - e_a)
            new[b] += K * (0 - (1 - e_a))
    return new
