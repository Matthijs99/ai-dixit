"""Player protocol + Pydantic move schemas + the validate/retry pipeline."""

from __future__ import annotations

import json
import logging
import random
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from dixit_ai.cards import Card, CardId, card_image_path

log = logging.getLogger(__name__)


class MoveError(Exception):
    """Raised when a player fails to produce a valid move after retry."""


class Player(Protocol):
    model_id: str
    display_name: str
    org: str

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]: ...
    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId: ...
    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId: ...


# ----- Pydantic move schemas (adapter-internal) -----

class StoryMove(BaseModel):
    card: str
    clue: str = Field(min_length=1, max_length=140)


class PickMove(BaseModel):
    card: str


class VoteMove(BaseModel):
    card: str
    reasoning: str | None = Field(default=None, max_length=200)


# ----- Labeling -----

@dataclass
class LabeledHand:
    labels: dict[str, CardId]            # label → card id
    ordered_labels: list[str]            # the labels in their listed order

    @property
    def label_to_id(self) -> dict[str, CardId]:
        return self.labels


_ALPHABET = list(string.ascii_uppercase)


def _label_hand(cards: list[Card], seed: int | str | None = None) -> LabeledHand:
    """Assign freshly shuffled labels A, B, C, ... to the offered cards."""
    cards_shuffled = list(cards)
    rng = random.Random(seed)
    rng.shuffle(cards_shuffled)
    labels = _ALPHABET[: len(cards_shuffled)]
    mapping = {L: c.id for L, c in zip(labels, cards_shuffled)}
    return LabeledHand(labels=mapping, ordered_labels=labels)


# ----- Validation -----

def _validate_story(move: StoryMove, lh: LabeledHand) -> tuple[CardId, str]:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered labels {lh.ordered_labels}"
        )
    return lh.labels[move.card], move.clue


def _validate_pick(move: PickMove, lh: LabeledHand) -> CardId:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered labels {lh.ordered_labels}"
        )
    return lh.labels[move.card]


def _validate_vote(move: VoteMove, lh: LabeledHand, own_card_id: CardId) -> CardId:
    if move.card not in lh.labels:
        raise ValueError(
            f"card label {move.card!r} not in offered face-up labels {lh.ordered_labels}"
        )
    chosen = lh.labels[move.card]
    if chosen == own_card_id:
        raise ValueError(
            f"label {move.card!r} corresponds to your own card; you may not vote for it"
        )
    return chosen


# ----- BaseAdapter -----

@dataclass
class CallRecord:
    """Audit trail entry. One per SDK call."""
    turn: int | None
    phase: str
    model: str
    card_labels: dict[str, CardId]
    prompt: str
    response_raw: str
    parsed: dict | None
    attempts: int
    error: str | None = None


class BaseAdapter(ABC):
    model_id: str = "base"
    display_name: str = "base"
    org: str = "base"

    def __init__(self) -> None:
        self.audit: list[CallRecord] = []
        self._current_turn: int | None = None

    def set_turn(self, turn: int) -> None:
        self._current_turn = turn

    # Each concrete adapter implements _call.
    @abstractmethod
    def _call(
        self,
        *,
        messages: list[dict],
        schema: dict,
        image_bytes_by_label: dict[str, bytes],
    ) -> str:
        """Make one SDK call. Return the raw response text."""

    # ----- Public Player methods -----

    def storytell(self, hand: list[Card]) -> tuple[CardId, str]:
        lh = _label_hand(hand)
        from dixit_ai.prompts import SYSTEM_PRELUDE, storyteller_user
        return self._run(
            phase="storytell",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, storyteller_user(lh.ordered_labels)
            ),
            schema=_schema_for_labels(lh.ordered_labels, with_clue=True),
            validator=lambda m: _validate_story(StoryMove(**m), lh),
        )

    def pick_for_clue(self, hand: list[Card], clue: str) -> CardId:
        lh = _label_hand(hand)
        from dixit_ai.prompts import SYSTEM_PRELUDE, picker_user
        return self._run(
            phase="pick",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, picker_user(lh.ordered_labels, clue)
            ),
            schema=_schema_for_labels(lh.ordered_labels, with_clue=False),
            validator=lambda m: _validate_pick(PickMove(**m), lh),
        )

    def vote(
        self, face_up_cards: list[Card], clue: str, own_card_id: CardId
    ) -> CardId:
        lh = _label_hand(face_up_cards)
        own_label = next(L for L, cid in lh.labels.items() if cid == own_card_id)
        from dixit_ai.prompts import SYSTEM_PRELUDE, voter_user
        return self._run(
            phase="vote",
            lh=lh,
            messages=self._build_messages(
                SYSTEM_PRELUDE, voter_user(lh.ordered_labels, clue, own_label)
            ),
            schema=_schema_for_vote(lh.ordered_labels, own_label),
            validator=lambda m: _validate_vote(VoteMove(**m), lh, own_card_id),
        )

    # ----- Internals -----

    def _build_messages(self, system: str, user: str) -> list[dict]:
        """A provider-neutral message shape. Adapters reshape this as needed."""
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _run(self, *, phase, lh, messages, schema, validator):
        image_bytes_by_label: dict[str, bytes] = {}
        for label, cid in lh.labels.items():
            image_bytes_by_label[label] = card_image_path(cid).read_bytes()

        last_error: str | None = None

        for attempt in (1, 2):
            t0 = time.monotonic()
            try:
                raw = self._call(
                    messages=messages,
                    schema=schema,
                    image_bytes_by_label=image_bytes_by_label,
                )
            except Exception as exc:
                last_error = f"sdk error: {exc}"
                log.warning(
                    "    %s %s try %d failed: %s",
                    self.model_id, phase, attempt, last_error,
                )
                self._record(phase, lh, "<sdk error>", "", None, attempt, last_error)
                continue
            dt = time.monotonic() - t0

            try:
                parsed = _loose_parse(raw)
            except Exception as exc:
                last_error = f"json parse: {exc}"
                log.warning(
                    "    %s %s try %d bad json (%.1fs): %s",
                    self.model_id, phase, attempt, dt, last_error,
                )
                self._record(phase, lh, messages_text(messages), raw, None, attempt, last_error)
                messages = _append_retry_turn(messages, raw, last_error)
                continue

            try:
                result = validator(parsed)
            except (ValidationError, ValueError) as exc:
                last_error = f"validation: {exc}"
                log.warning(
                    "    %s %s try %d illegal (%.1fs): %s",
                    self.model_id, phase, attempt, dt, last_error,
                )
                self._record(phase, lh, messages_text(messages), raw, parsed, attempt, last_error)
                messages = _append_retry_turn(messages, raw, last_error)
                continue

            log.info("    %s %s ok (%.1fs)", self.model_id, phase, dt)
            self._record(phase, lh, messages_text(messages), raw, parsed, attempt, None)
            return result

        raise MoveError(f"{self.model_id} {phase} failed after 2 attempts: {last_error}")

    def _record(self, phase, lh, prompt, raw, parsed, attempts, error):
        self.audit.append(
            CallRecord(
                turn=self._current_turn,
                phase=phase,
                model=self.model_id,
                card_labels=dict(lh.labels),
                prompt=prompt,
                response_raw=raw,
                parsed=parsed,
                attempts=attempts,
                error=error,
            )
        )


# ----- Helpers -----

def _schema_for_labels(labels: list[str], *, with_clue: bool) -> dict:
    if with_clue:
        return {
            "type": "object",
            "properties": {
                "card": {"type": "string", "enum": labels},
                "clue": {"type": "string", "maxLength": 140, "minLength": 1},
            },
            "required": ["card", "clue"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {"card": {"type": "string", "enum": labels}},
        "required": ["card"],
        "additionalProperties": False,
    }


def _schema_for_vote(labels: list[str], own_label: str) -> dict:
    allowed = [L for L in labels if L != own_label]
    return {
        "type": "object",
        "properties": {
            "card": {"type": "string", "enum": allowed},
            "reasoning": {"type": "string", "maxLength": 200},
        },
        "required": ["card"],
        "additionalProperties": False,
    }


def _loose_parse(raw: str) -> dict:
    raw = raw.strip()
    # Strip ```json fences if present.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip().rstrip("`")
    return json.loads(raw)


def messages_text(messages: list[dict]) -> str:
    return json.dumps(messages, default=str)


def _append_retry_turn(messages: list[dict], raw: str, error: str) -> list[dict]:
    return messages + [
        {"role": "assistant", "content": raw},
        {
            "role": "user",
            "content": (
                f"Your response was rejected: {error}. "
                f"Respond again with valid JSON that matches the schema exactly."
            ),
        },
    ]
