import json
import pytest

from dixit_ai.storage import (
    load_stats, save_stats, load_index, append_index,
    save_game, game_exists,
)

def test_data_dir_resolves_to_repo_data(tmp_path, monkeypatch):
    # We patch DATA_DIR so we don't touch the real data/.
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    assert tmp_path.exists()

def test_save_and_load_stats(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    payload = {
        "updated_at": "2026-05-22T03:14:00Z",
        "models": {
            "m1": {"display_name": "M1", "org": "X", "games": 0, "wins": 0, "points": 0},
        },
    }
    save_stats(payload)
    assert (tmp_path / "stats.json").exists()
    loaded = load_stats()
    assert loaded == payload

def test_append_index_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "index.json").write_text("[]")
    row = {"game_id": "2026-05-22", "status": "complete"}
    append_index(row)
    rows = load_index()
    assert rows == [row]

def test_save_game_writes_two_files(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    save_game(
        game_id="2026-05-22",
        game_doc={"game_id": "2026-05-22", "turns": []},
        raw_lines=[{"foo": "bar"}],
    )
    assert (tmp_path / "games" / "2026-05-22.json").exists()
    raw = (tmp_path / "games" / "2026-05-22.raw.jsonl").read_text().splitlines()
    assert len(raw) == 1
    assert json.loads(raw[0]) == {"foo": "bar"}

def test_save_game_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    save_game(game_id="2026-05-22", game_doc={"x": 1}, raw_lines=[])
    with pytest.raises(FileExistsError):
        save_game(game_id="2026-05-22", game_doc={"x": 2}, raw_lines=[])

def test_game_exists(tmp_path, monkeypatch):
    monkeypatch.setattr("dixit_ai.storage.DATA_DIR", tmp_path)
    (tmp_path / "games").mkdir()
    assert not game_exists("2026-05-22")
    save_game(game_id="2026-05-22", game_doc={"x": 1}, raw_lines=[])
    assert game_exists("2026-05-22")
