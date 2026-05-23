"""Mistral Medium 3.5 adapter via response_format=json_object."""

from __future__ import annotations

import base64
import os
from typing import Any

from mistralai.client import Mistral

from dixit_ai.players.base import BaseAdapter


class MistralPlayer(BaseAdapter):
    org = "Mistral"

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
        self.client = client or Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        # Pixtral takes content as a list of mixed text+image parts.
        schema_hint = (
            "\n\nYour response MUST be valid JSON matching this schema:\n"
            f"{schema}"
        )
        content_parts: list[dict] = [{"type": "text", "text": first_user + schema_hint}]
        for label, blob in image_bytes_by_label.items():
            b64 = base64.b64encode(blob).decode()
            content_parts.append({"type": "text", "text": f"Card {label}:"})
            content_parts.append(
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64}"}
            )

        ms_messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content_parts},
        ]
        for m in messages:
            if m["role"] == "system" or m["content"] == first_user:
                continue
            ms_messages.append(m)

        resp = self.client.chat.complete(
            model=self.model_id,
            messages=ms_messages,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"
