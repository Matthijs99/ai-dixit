"""Glicko-2 ratings (the system Lichess uses; see glicko2.pdf).

Each Dixit game is one rating period: every participant is compared against
each of the others once, and the pairwise result is decided by final score
(higher = win, equal = draw). Ratings live on the familiar ~1500 Elo scale;
alongside each rating we track a rating deviation (RD, the confidence ±) and
a volatility.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Iterable, Mapping, Sequence

INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_VOL = 0.06
TAU = 0.5  # volatility constraint; Glickman's canonical default
SCALE = 173.7178  # Glicko-2 internal scale factor

log = logging.getLogger(__name__)

State = tuple[float, float, float]  # (rating, rd, vol)


# ----- Roster bookkeeping -----

def _new_entry(player: Any) -> dict:
    return {
        "display_name": player.display_name,
        "org": player.org,
        "rating": INITIAL_RATING,
        "rd": INITIAL_RD,
        "vol": INITIAL_VOL,
        "games": 0,
        "wins": 0,
    }


def _init_or_inherit(models: dict, player: Any) -> None:
    """Create an entry for `player` if missing, inheriting from a prior id."""
    if player.model_id in models:
        return
    prior = next(
        (pid for pid in getattr(player, "previous_ids", []) if pid in models),
        None,
    )
    if prior is not None:
        src = models[prior]
        log.info(
            "elo: %s inheriting from %s (rating=%.2f, rd=%.2f, games=%d, wins=%d)",
            player.model_id, prior, src["rating"], src["rd"], src["games"], src["wins"],
        )
        models[player.model_id] = {
            "display_name": player.display_name,
            "org": player.org,
            "rating": src["rating"],
            "rd": src["rd"],
            "vol": src["vol"],
            "games": src["games"],
            "wins": src["wins"],
        }
    else:
        log.info("elo: initializing %s at %.0f", player.model_id, INITIAL_RATING)
        models[player.model_id] = _new_entry(player)


def _reconcile_retired(models: dict, active_ids: set[str]) -> None:
    """Tag entries not in the active roster `retired`; clear the flag otherwise."""
    for model_id, entry in models.items():
        if model_id in active_ids:
            entry.pop("retired", None)
        else:
            entry["retired"] = True


def ensure_model_entries(elo: dict, players: Iterable[Any]) -> None:
    """Make sure every player has an entry in elo["models"].

    New players inherit rating/RD/volatility/games/wins from the first matching
    `previous_ids` entry that is present, else start fresh. The original entry
    is kept (as a retired record) so historical games keep resolving. Entries
    absent from the active roster are flagged `retired` so the leaderboard can
    hide them. Mutates `elo` in place.
    """
    players = list(players)
    models = elo.setdefault("models", {})
    for p in players:
        _init_or_inherit(models, p)
    _reconcile_retired(models, {p.model_id for p in players})


# ----- Glicko-2 core -----

def glicko2_update(
    rating: float,
    rd: float,
    vol: float,
    matches: Sequence[tuple[float, float, float]],
    *,
    tau: float = TAU,
) -> State:
    """One Glicko-2 rating period for a single player.

    `matches` is a sequence of (opponent_rating, opponent_rd, score) where score
    is 1.0 (win), 0.5 (draw) or 0.0 (loss). Returns the new (rating, rd, vol).
    Follows the step numbering in Glickman's paper.
    """
    mu = (rating - INITIAL_RATING) / SCALE
    phi = rd / SCALE

    if not matches:
        # Step 6 only: no games this period, RD inflates by the volatility.
        phi_star = math.sqrt(phi * phi + vol * vol)
        return (rating, phi_star * SCALE, vol)

    # Steps 3-4: estimate variance v and the score-weighted improvement.
    v_inv = 0.0
    delta_sum = 0.0
    for opp_rating, opp_rd, score in matches:
        mu_j = (opp_rating - INITIAL_RATING) / SCALE
        phi_j = opp_rd / SCALE
        g = 1.0 / math.sqrt(1.0 + 3.0 * phi_j * phi_j / (math.pi ** 2))
        e = 1.0 / (1.0 + math.exp(-g * (mu - mu_j)))
        v_inv += g * g * e * (1.0 - e)
        delta_sum += g * (score - e)
    v = 1.0 / v_inv
    delta = v * delta_sum

    # Step 5: iterate to the new volatility (Illinois/regula-falsi).
    a = math.log(vol * vol)

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    A = a
    if delta * delta > phi * phi + v:
        B = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        B = a - k * tau
    fA, fB = f(A), f(B)
    while abs(B - A) > 1e-6:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA /= 2.0
        B, fB = C, fC
    new_vol = math.exp(A / 2.0)

    # Step 6-7: new RD and rating.
    phi_star = math.sqrt(phi * phi + new_vol * new_vol)
    new_phi = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    new_mu = mu + new_phi * new_phi * delta_sum
    return (new_mu * SCALE + INITIAL_RATING, new_phi * SCALE, new_vol)


def update_ratings(
    states: Mapping[str, State],
    scores: Mapping[str, int],
) -> dict[str, State]:
    """Apply one game as a Glicko-2 rating period.

    `states` maps model_id -> (rating, rd, vol); `scores` is the final score
    map. Each model is scored against every other (win/draw/loss by points),
    using the frozen pre-game states, so update order doesn't matter. The input
    is not mutated.
    """
    base = dict(states)
    ids = list(base)
    out: dict[str, State] = {}
    for i in ids:
        rating, rd, vol = base[i]
        matches = []
        for j in ids:
            if j == i:
                continue
            opp_rating, opp_rd, _ = base[j]
            si, sj = scores.get(i, 0), scores.get(j, 0)
            score = 0.5 if si == sj else (1.0 if si > sj else 0.0)
            matches.append((opp_rating, opp_rd, score))
        out[i] = glicko2_update(rating, rd, vol, matches)
    return out
