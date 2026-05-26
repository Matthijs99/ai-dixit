"""ByteDance Seed adapter — reached via OpenRouter (OpenAI-compatible).

ByteDance's Seed models have no clean first-party English API, so we route
through OpenRouter. Model ids therefore carry the OpenRouter vendor prefix
(e.g. ``bytedance/dola-seed-2.0-pro``).
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from dixit_ai.players.openai import OpenAIPlayer

BASE_URL = "https://openrouter.ai/api/v1"


class BytedancePlayer(OpenAIPlayer):
    org = "Bytedance"

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
            client=client
            or OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url=BASE_URL),
        )
