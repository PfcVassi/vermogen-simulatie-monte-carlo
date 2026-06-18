"""Lokaal opslaan en laden van scenario's (JSON in .scenarios/)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent / ".scenarios"


def _ensure_dir() -> Path:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    return SCENARIOS_DIR


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.strip().lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug or "scenario"


def list_scenarios() -> list[dict]:
    _ensure_dir()
    items: list[dict] = []
    for path in sorted(SCENARIOS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            data["_id"] = path.stem
            items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return items


def save_scenario(payload: dict) -> str:
    _ensure_dir()
    name = str(payload.get("name", "scenario")).strip() or "scenario"
    payload = {**payload, "name": name, "saved_at": datetime.now(timezone.utc).isoformat()}
    base = _slug(name)
    path = SCENARIOS_DIR / f"{base}.json"
    counter = 2
    while path.exists() and json.loads(path.read_text(encoding="utf-8")).get("name") != name:
        path = SCENARIOS_DIR / f"{base}-{counter}.json"
        counter += 1
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.stem


def load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' niet gevonden.")
    return json.loads(path.read_text(encoding="utf-8"))


def delete_scenario(scenario_id: str) -> None:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if path.exists():
        path.unlink()
