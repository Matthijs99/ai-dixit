"""ByteDance Seed adapter — BytePlus ModelArk (OpenAI-compatible).

ModelArk exposes an OpenAI-compatible endpoint, so this subclasses OpenAIPlayer
with the ModelArk base URL. Model ids are the ModelArk ids, e.g.
``seed-2-0-pro-260328``. Reads the key from BYTEPLUS_API_KEY (or ARK_API_KEY).
"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from dixit_ai.players.openai import OpenAIPlayer

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"


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
            or OpenAI(
                api_key=os.environ.get("BYTEPLUS_API_KEY") or os.environ["ARK_API_KEY"],
                base_url=BASE_URL,
            ),
        )
