"""Google Gemini adapter via response_schema."""

from __future__ import annotations

import os
from typing import Any

from google import genai

from dixit_ai.players.base import BaseAdapter, strip_for_gemini

MODEL = "gemini-2.5-pro"


class GeminiPlayer(BaseAdapter):
    model_id = MODEL
    display_name = "Gemini 2.5 Pro"
    org = "Google"

    def __init__(self, client: Any = None) -> None:
        super().__init__()
        self.client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def _call(self, *, messages, schema, image_bytes_by_label) -> str:
        from google.genai.types import Part, GenerateContentConfig

        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        first_user = next(m["content"] for m in messages if m["role"] == "user")

        parts: list[Any] = [Part.from_text(text=first_user)]
        for label, blob in image_bytes_by_label.items():
            parts.append(Part.from_text(text=f"Card {label}:"))
            parts.append(Part.from_bytes(data=blob, mime_type="image/jpeg"))

        # Append retry turns as additional text parts.
        for m in messages:
            if m["role"] == "system" or m["content"] == first_user:
                continue
            parts.append(Part.from_text(text=f"[{m['role']}] {m['content']}"))

        config = GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=strip_for_gemini(schema),
        )

        resp = self.client.models.generate_content(
            model=MODEL,
            contents=parts,
            config=config,
        )
        return resp.text or "{}"
