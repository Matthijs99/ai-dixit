"""Game engine: pure Dixit rules. No LLM SDK imports."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from dixit_ai.cards import Card, CardId, Deck
from dixit_ai.players.base import MoveError, Player

log = logging.getLogger(__name__)


ModelId = str


HAND_SIZE = 6
WIN_SCORE = 30
TURN_LIMIT = 50


def score_turn(
    storyteller: ModelId,
    storyteller_card: CardId,
    submissions: Mapping[ModelId, CardId],
    votes: Mapping[ModelId, CardId],
) -> dict[ModelId, int]:
    """Apply Dixit scoring rules for a single turn.

    `submissions` maps every player who put a card on the table (including
    storyteller) to their card id. Pick forfeiters are omitted.

    `votes` maps every non-storyteller who voted to the card id they voted for.
    Vote forfeiters and pick forfeiters are omitted.

    Returns the delta for EVERY player named in `submissions`. Pick forfeiters
    are NOT in the result; the caller handles them with a zero delta.
    """
    delta: dict[ModelId, int] = {p: 0 for p in submissions}

    # Voters who participated (i.e., have a vote recorded).
    participants = [v for v in votes if v != storyteller]
    correct_votes = sum(1 for v in participants if votes[v] == storyteller_card)
    all_or_none = (
        participants
        and (correct_votes == 0 or correct_votes == len(participants))
    )

    if all_or_none:
        delta[storyteller] = 0
        for v in participants:
            delta[v] += 2
    else:
        delta[storyteller] = 3
        for v in participants:
            if votes[v] == storyteller_card:
                delta[v] += 3

    # Decoy bonus: every non-storyteller who submitted a card gets +1 per vote
    # their card received, capped at +3.
    for owner, card in submissions.items():
        if owner == storyteller:
            continue
        bonus = sum(1 for v_card in votes.values() if v_card == card)
        delta[owner] += min(bonus, 3)

    return delta


@dataclass
class TurnRecord:
    turn: int
    storyteller: ModelId
    clue: str | None
    storyteller_card: CardId | None
    submissions: dict[ModelId, CardId]
    face_up_order: list[CardId]
    votes: dict[ModelId, CardId]
    scores_delta: dict[ModelId, int]
    scores_total: dict[ModelId, int]
    degraded: list[str] = field(default_factory=list)


@dataclass
class GameResult:
    turns: list[TurnRecord]
    final_scores: dict[ModelId, int]
    winner: ModelId | None
    status: str  # "complete" or "turn_limit"
    play_order: list[ModelId] = field(default_factory=list)
    hand_size_snapshots: list[dict[ModelId, int]] = field(default_factory=list)


def play_game(players: Sequence[Player], rng_seed: str = "default") -> GameResult:
    """Play one full Dixit game and return a GameResult."""

    rng = random.Random(rng_seed)

    # Randomise who goes first using the same date-seeded RNG, so the
    # rotation is reproducible from the seed alone.
    shuffled_players = list(players)
    rng.shuffle(shuffled_players)

    deck = Deck(rng=rng)
    hands: dict[ModelId, list[Card]] = {
        p.model_id: deck.deal(HAND_SIZE) for p in shuffled_players
    }
    totals: dict[ModelId, int] = {p.model_id: 0 for p in shuffled_players}
    turns: list[TurnRecord] = []
    hand_snapshots: list[dict[ModelId, int]] = []

    by_id = {p.model_id: p for p in shuffled_players}
    order = [p.model_id for p in shuffled_players]
    display_names = {p.model_id: getattr(p, "display_name", p.model_id) for p in players}
    history: list[str] = []

    def _broadcast_state(turn: int) -> None:
        for p in players:
            if hasattr(p, "set_state"):
                p.set_state(
                    turn=turn,
                    lineup=order,
                    display_names=display_names,
                    scoreboard=dict(totals),
                    history=list(history),
                )

    def _summarise_turn(record: TurnRecord) -> str:
        """One-line plain-text summary of a completed turn for downstream prompts."""
        st = display_names.get(record.storyteller, record.storyteller)
        if record.clue is None:
            return f"turn {record.turn + 1} · {st}: forfeited (no clue)"

        participants = [
            pid for pid in record.votes
        ]
        correct = sum(
            1 for v in record.votes.values() if v == record.storyteller_card
        )
        if not participants:
            outcome = "no votes recorded"
        elif correct == 0:
            outcome = "no one guessed (all-or-none)"
        elif correct == len(participants):
            outcome = "everyone guessed (all-or-none)"
        else:
            outcome = f"partial: {correct}/{len(participants)} guessed"

        deltas = ", ".join(
            f"{display_names.get(pid, pid)}={record.scores_delta.get(pid, 0):+d}"
            for pid in order
        )
        suffix = f" [degraded: {', '.join(record.degraded)}]" if record.degraded else ""
        return (
            f"turn {record.turn + 1} · {st}: \"{record.clue}\" · {outcome} · {deltas}{suffix}"
        )

    log.info("game start · seed=%s · players=%s", rng_seed, order)

    turn_index = 0
    status = "turn_limit"

    while turn_index < TURN_LIMIT:
        if any(score >= WIN_SCORE for score in totals.values()):
            status = "complete"
            break

        _broadcast_state(turn_index)
        storyteller_id = order[turn_index % len(order)]
        storyteller = by_id[storyteller_id]
        log.info("turn %d · storyteller=%s", turn_index + 1, storyteller_id)

        record = TurnRecord(
            turn=turn_index,
            storyteller=storyteller_id,
            clue=None,
            storyteller_card=None,
            submissions={},
            face_up_order=[],
            votes={},
            scores_delta={p: 0 for p in totals},
            scores_total=dict(totals),
            degraded=[],
        )

        # a. Storyteller move.
        try:
            story_card_id, clue = storyteller.storytell(list(hands[storyteller_id]))
        except MoveError:
            record.degraded.append(f"{storyteller_id}:storytell:forfeit")
            turns.append(record)
            history.append(_summarise_turn(record))
            hand_snapshots.append({m: len(h) for m, h in hands.items()})
            turn_index += 1
            continue

        # Validate storyteller's card is in their hand.
        if not any(c.id == story_card_id for c in hands[storyteller_id]):
            record.degraded.append(f"{storyteller_id}:storytell:illegal")
            turns.append(record)
            history.append(_summarise_turn(record))
            hand_snapshots.append({m: len(h) for m, h in hands.items()})
            turn_index += 1
            continue

        record.clue = clue
        record.storyteller_card = story_card_id
        record.submissions[storyteller_id] = story_card_id
        log.info("  clue: %r (card %d)", clue, story_card_id)

        # b. Other players pick.
        for pid in order:
            if pid == storyteller_id:
                continue
            try:
                picked = by_id[pid].pick_for_clue(list(hands[pid]), clue)
            except MoveError:
                record.degraded.append(f"{pid}:pick:forfeit")
                continue
            if not any(c.id == picked for c in hands[pid]):
                record.degraded.append(f"{pid}:pick:illegal")
                continue
            record.submissions[pid] = picked

        # c. Shuffle face-up reveal order.
        face_up_ids = list(record.submissions.values())
        rng.shuffle(face_up_ids)
        record.face_up_order = face_up_ids
        face_up_cards = [Card(id=cid) for cid in face_up_ids]

        # d. Voting.
        for pid in order:
            if pid == storyteller_id:
                continue
            if pid not in record.submissions:
                continue  # this player sat out the whole turn
            own_card = record.submissions[pid]
            try:
                voted = by_id[pid].vote(face_up_cards, clue, own_card)
            except MoveError:
                record.degraded.append(f"{pid}:vote:forfeit")
                continue
            if voted not in face_up_ids or voted == own_card:
                record.degraded.append(f"{pid}:vote:illegal")
                continue
            record.votes[pid] = voted

        # e. Score.
        delta = score_turn(
            storyteller_id, story_card_id, record.submissions, record.votes
        )
        # Pre-populate delta for any player not in submissions (pick forfeiters).
        for pid in order:
            delta.setdefault(pid, 0)
            totals[pid] += delta[pid]
        record.scores_delta = delta
        record.scores_total = dict(totals)
        log.info(
            "  scores: %s%s",
            ", ".join(f"{p}={totals[p]}({delta[p]:+d})" for p in order),
            f" · degraded: {record.degraded}" if record.degraded else "",
        )

        # f. Played cards → discard, and remove from each owner's hand.
        for cid in record.submissions.values():
            deck.discard.append(Card(id=cid))
        for pid, played in record.submissions.items():
            hands[pid] = [c for c in hands[pid] if c.id != played]

        # g. Refill each hand to HAND_SIZE.
        for pid in order:
            while len(hands[pid]) < HAND_SIZE:
                c = deck.draw_one()
                if c is None:
                    break
                hands[pid].append(c)

        turns.append(record)
        history.append(_summarise_turn(record))
        hand_snapshots.append({m: len(h) for m, h in hands.items()})
        turn_index += 1

    winner = max(totals, key=lambda p: totals[p]) if totals else None
    log.info(
        "game end · status=%s · winner=%s · final=%s",
        status,
        winner,
        ", ".join(f"{p}={totals[p]}" for p in order),
    )
    return GameResult(
        turns=turns,
        final_scores=dict(totals),
        winner=winner,
        status=status,
        play_order=list(order),
        hand_size_snapshots=hand_snapshots,
    )
