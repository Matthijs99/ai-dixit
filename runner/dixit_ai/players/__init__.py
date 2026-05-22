"""The fixed lineup of five players for the nightly game."""

from __future__ import annotations

from dixit_ai.players.claude import ClaudePlayer
from dixit_ai.players.openai import OpenAIPlayer
from dixit_ai.players.gemini import GeminiPlayer
from dixit_ai.players.grok import GrokPlayer
from dixit_ai.players.mistral import MistralPlayer


def default_lineup():
    """Instantiate the five flagship players. Reads API keys from env."""
    return [
        ClaudePlayer(),
        OpenAIPlayer(),
        GeminiPlayer(),
        GrokPlayer(),
        MistralPlayer(),
    ]
