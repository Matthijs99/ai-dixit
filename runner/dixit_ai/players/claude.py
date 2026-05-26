"""Anthropic Claude adapter via tool use."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from anthropic import Anthropic

from dixit_ai.players.base import BaseAdapter


class ClaudePlayer(BaseAdapter):
    org = "Anthropic"

    # Extended-thinking budget (tokens). Kept modest to cap nightly cost.
    THINKING_BUDGET = 1536

    def __init__(
        self,
        *,
        model_id: str,
        display_name: str,
        thinking: bool = False,
        client: Any = None,
    ) -> None:
        super().__init__()
        self.model_id = model_id
        self.display_name = display_name
        self.thinking = thinking
        self.client = client or Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs: list[dict] = []

        # Build the first user message: text + every card image.
        first_user_text = next(m["content"] for m in messages if m["role"] == "user")
        content_blocks: list[dict] = [{"type": "text", "text": first_user_text}]
        for label, blob in image_bytes_by_label.items():
            content_blocks.append({"type": "text", "text": f"Card {label}:"})
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(blob).decode(),
                    },
                }
            )
        user_msgs.append({"role": "user", "content": content_blocks})

        # Append any retry turns (assistant + user pairs).
        for m in messages:
            if m["role"] == "assistant":
                user_msgs.append({"role": "assistant", "content": m["content"]})
            elif m["role"] == "user" and m["content"] != first_user_text:
                user_msgs.append({"role": "user", "content": m["content"]})

        tool = {
            "name": "submit_move",
            "description": "Submit your move by calling this tool.",
            "input_schema": schema,
        }

        # "-thinking" is part of the identity (matches the leaderboard row), not a
        # real API model id; thinking is a request param. Strip it for the call.
        api_model = self.model_id.removesuffix("-thinking")
        kwargs: dict[str, Any] = {
            "model": api_model,
            "max_tokens": 512,
            "system": system,
            "tools": [tool],
            # Forced tool_choice is incompatible with extended thinking, so when
            # thinking is on we must let the model choose (auto). It reliably
            # calls the only available tool; _loose text parsing is the fallback.
            "tool_choice": {"type": "auto"},
            "messages": user_msgs,
        }
        if self.thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.THINKING_BUDGET,
            }
            # max_tokens must exceed the thinking budget and leave room for output.
            kwargs["max_tokens"] = self.THINKING_BUDGET + 512
        else:
            # Without thinking we can force the tool for a guaranteed structured call.
            kwargs["tool_choice"] = {"type": "tool", "name": "submit_move"}

        resp = self.client.messages.create(**kwargs)

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        # Fallback: return raw text if no tool block.
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return "{}"
