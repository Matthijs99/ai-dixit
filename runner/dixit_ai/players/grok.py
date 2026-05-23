"""xAI Grok adapter — OpenAI-compatible, different base URL."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from dixit_ai.players.openai import OpenAIPlayer

BASE_URL = "https://api.x.ai/v1"


class GrokPlayer(OpenAIPlayer):
    org = "xAI"

    def __init__(
        self,
        *,
        model_id: str,
        display_name: str,
        client: Any = None,
    ) -> None:
        super().__init__(
            model_id=model_id,
            display_name=display_name,
            client=client or OpenAI(api_key=os.environ["XAI_API_KEY"], base_url=BASE_URL),
        )
