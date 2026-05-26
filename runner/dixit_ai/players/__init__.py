"""Load the player lineup from models.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from dixit_ai.cards import REPO_ROOT
from dixit_ai.players.bytedance import BytedancePlayer
from dixit_ai.players.claude import ClaudePlayer
from dixit_ai.players.gemini import GeminiPlayer
from dixit_ai.players.grok import GrokPlayer
from dixit_ai.players.mistral import MistralPlayer
from dixit_ai.players.moonshot import MoonshotPlayer
from dixit_ai.players.openai import OpenAIPlayer

_ADAPTERS: dict[str, type] = {
    "claude": ClaudePlayer,
    "openai": OpenAIPlayer,
    "gemini": GeminiPlayer,
    "grok": GrokPlayer,
    "mistral": MistralPlayer,
    "bytedance": BytedancePlayer,
    "moonshot": MoonshotPlayer,
}

# Adapters that accept a `thinking` constructor kwarg.
_THINKING_ADAPTERS = {"claude"}


def _models_yaml_path() -> Path:
    override = os.environ.get("DIXIT_MODELS_YAML")
    if override:
        return Path(override)
    return REPO_ROOT / "models.yaml"


def load_roster(path: Path | None = None) -> list[dict[str, Any]]:
    """Return the raw list of player entries from the YAML file."""
    path = path or _models_yaml_path()
    doc = yaml.safe_load(path.read_text()) or {}
    entries = doc.get("players")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: expected a non-empty top-level 'players' list")
    return entries


def default_lineup(path: Path | None = None) -> list:
    """Instantiate the configured players. Reads API keys from env."""
    players: list = []
    for i, entry in enumerate(load_roster(path)):
        adapter = entry.get("adapter")
        model_id = entry.get("model_id")
        display_name = entry.get("display_name")
        if not adapter or not model_id or not display_name:
            raise ValueError(
                f"models.yaml entry #{i}: each player needs "
                f"'adapter', 'model_id', and 'display_name' (got {entry!r})"
            )
        cls = _ADAPTERS.get(adapter)
        if cls is None:
            raise ValueError(
                f"models.yaml entry #{i}: unknown adapter {adapter!r}; "
                f"known: {sorted(_ADAPTERS)}"
            )
        kwargs: dict[str, Any] = {"model_id": model_id, "display_name": display_name}
        if adapter in _THINKING_ADAPTERS and entry.get("thinking"):
            kwargs["thinking"] = True
        player = cls(**kwargs)
        # Attach previous_ids for the Elo carryover layer to consult.
        player.previous_ids = list(entry.get("previous_ids") or [])
        # Attach a stable fallback model, resolved by player.resolve() before play.
        player.fallback_model_id = entry.get("fallback")
        player.fallback_display_name = entry.get("fallback_display_name")
        players.append(player)
    return players
