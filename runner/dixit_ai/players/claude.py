"""Anthropic Claude adapter via tool use."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from dixit_ai.players.base import BaseAdapter

MODEL = "claude-opus-4-7"


class ClaudePlayer(BaseAdapter):
    model_id = MODEL
    display_name = "Claude Opus 4.7"
    org = "Anthropic"

    def __init__(self, client: Any = None) -> None:
        super().__init__()
        if client is None:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.client = client

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
            "description": "Submit your move.",
            "input_schema": schema,
        }

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit_move"},
            messages=user_msgs,
        )

        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return json.dumps(block.input)
        # Fallback: return raw text if no tool block.
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return "{}"
