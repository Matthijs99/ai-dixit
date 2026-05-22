"""xAI Grok adapter — OpenAI-compatible, different base URL."""

from __future__ import annotations

import os
from typing import Any

from dixit_ai.players.openai import OpenAIPlayer

MODEL = "grok-4.3"
BASE_URL = "https://api.x.ai/v1"


class GrokPlayer(OpenAIPlayer):
    model_id = MODEL
    display_name = "Grok 4.3"
    org = "xAI"

    def __init__(self, client: Any = None) -> None:
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=BASE_URL)
        super().__init__(client=client, model=MODEL)
