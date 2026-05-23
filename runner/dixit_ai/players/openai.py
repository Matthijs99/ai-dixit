"""OpenAI GPT adapter via structured outputs (JSON Schema, strict)."""

from __future__ import annotations

import base64
import os
from typing import Any

from openai import OpenAI

from dixit_ai.players.base import BaseAdapter


class OpenAIPlayer(BaseAdapter):
    org = "OpenAI"

    def __init__(
        self,
        *,
        model_id: str,
        display_name: str,
        client: Any = None,
    ) -> None:
        super().__init__()
        self.model_id = model_id
        self.display_name = display_name
        self.client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        # Build content array with text + images.
        content_parts: list[dict] = [{"type": "text", "text": first_user}]
        for label, blob in image_bytes_by_label.items():
            b64 = base64.b64encode(blob).decode()
            content_parts.append({"type": "text", "text": f"Card {label}:"})
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )

        oa_messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]
        # Append retry turns.
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "user" and m["content"] == first_user:
                continue
            oa_messages.append(m)

        resp = self.client.chat.completions.create(
            model=self.model_id,
            messages=oa_messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "submit_move",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        return resp.choices[0].message.content or "{}"
