"""Read/write the JSON files in data/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dixit_ai.cards import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=False) + "\n")


def load_stats() -> dict:
    return _read_json(DATA_DIR / "stats.json")


def save_stats(payload: dict) -> None:
    _write_json(DATA_DIR / "stats.json", payload)


def load_index() -> list:
    path = DATA_DIR / "index.json"
    if not path.exists():
        return []
    return _read_json(path)


def append_index(row: dict) -> None:
    rows = load_index()
    rows.append(row)
    _write_json(DATA_DIR / "index.json", rows)


def game_exists(game_id: str) -> bool:
    return (DATA_DIR / "games" / f"{game_id}.json").exists()


def save_game(*, game_id: str, game_doc: dict, raw_lines: list[dict]) -> None:
    games_dir = DATA_DIR / "games"
    games_dir.mkdir(parents=True, exist_ok=True)
    game_path = games_dir / f"{game_id}.json"
    raw_path = games_dir / f"{game_id}.raw.jsonl"
    if game_path.exists():
        raise FileExistsError(f"refusing to overwrite {game_path}")
    _write_json(game_path, game_doc)
    raw_path.write_text("".join(json.dumps(line) + "\n" for line in raw_lines))
