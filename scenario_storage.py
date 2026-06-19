"""Opslag, import en export van scenario-instellingen als JSON."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simulation_engine import CONTRIBUTION_FREQUENCIES

SCENARIOS_DIR = Path(__file__).parent / ".scenarios"
SCENARIO_SCHEMA_VERSION = 1
EXPORT_FILENAME = "monte_carlo_scenario.json"

VALID_WITHDRAWAL_TYPES = ("maandelijks", "jaarlijks")
VALID_N_RUNS = (1_000, 2_500, 5_000, 10_000)

REQUIRED_ROOT_KEYS = (
    "name",
    "tax_mode",
    "fiscaal_partner",
    "start_capital",
    "goal_label",
    "goal_amount",
    "inflation_pct",
    "n_runs",
    "phases",
)

REQUIRED_PHASE_KEYS = (
    "name",
    "years",
    "mu_pct",
    "sigma_pct",
    "contribution_amount",
    "contribution_frequency",
    "contribution_increase_pct",
    "extra_contribution_yearly",
    "withdrawal",
    "withdrawal_type",
    "index_withdrawal",
)


class ScenarioImportError(ValueError):
    """Ongeldig of incompleet scenario-bestand."""


def _ensure_dir() -> Path:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    return SCENARIOS_DIR


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.strip().lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug or "scenario"


def safe_download_filename(name: str) -> str:
    """Converteer scenarionaam naar veilige bestandsnaam (bijv. mijn_pensioen_plan.json)."""
    base = name.strip().lower().replace(" ", "_")
    base = re.sub(r"[^\w_-]", "", base).strip("_")
    return f"{base or 'scenario'}.json"


def _read_json_source(json_file: Any) -> str:
    if json_file is None:
        raise ScenarioImportError("Geen bestand ontvangen.")

    if hasattr(json_file, "getvalue"):
        raw = json_file.getvalue()
    elif hasattr(json_file, "read"):
        raw = json_file.read()
    elif isinstance(json_file, (bytes, bytearray)):
        raw = bytes(json_file)
    elif isinstance(json_file, str):
        raw = json_file.encode("utf-8")
    else:
        raise ScenarioImportError("Onbekend bestandstype.")

    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ScenarioImportError("Bestand is geen geldige UTF-8 tekst.") from exc

    return str(raw)


def _clamp_int(value: Any, field: str, lo: int, hi: int) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ScenarioImportError(f"Veld '{field}' moet een getal zijn.") from exc
    return max(lo, min(hi, num))


def _clamp_float(value: Any, field: str, lo: float, hi: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ScenarioImportError(f"Veld '{field}' moet een getal zijn.") from exc
    return max(lo, min(hi, num))


def _normalize_phase(raw: dict, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ScenarioImportError(f"Fase {index + 1} is geen geldig object.")

    missing = [key for key in REQUIRED_PHASE_KEYS if key not in raw]
    if missing:
        raise ScenarioImportError(
            f"Fase {index + 1} mist velden: {', '.join(missing)}."
        )

    freq = str(raw["contribution_frequency"])
    if freq not in CONTRIBUTION_FREQUENCIES:
        raise ScenarioImportError(
            f"Fase {index + 1}: ongeldige inlegfrequentie '{freq}'."
        )

    withdrawal_type = str(raw["withdrawal_type"])
    if withdrawal_type not in VALID_WITHDRAWAL_TYPES:
        raise ScenarioImportError(
            f"Fase {index + 1}: ongeldig opnametype '{withdrawal_type}'."
        )

    return {
        "id": str(raw.get("id") or uuid.uuid4().hex[:8]),
        "name": str(raw["name"]).strip() or f"fase {index + 1}",
        "years": _clamp_int(raw["years"], f"phases[{index}].years", 1, 50),
        "mu_pct": _clamp_float(raw["mu_pct"], f"phases[{index}].mu_pct", 0.0, 25.0),
        "sigma_pct": _clamp_float(raw["sigma_pct"], f"phases[{index}].sigma_pct", 0.0, 50.0),
        "contribution_amount": _clamp_int(
            raw["contribution_amount"], f"phases[{index}].contribution_amount", 0, 500_000,
        ),
        "contribution_frequency": freq,
        "contribution_increase_pct": _clamp_float(
            raw["contribution_increase_pct"], f"phases[{index}].contribution_increase_pct", 0.0, 15.0,
        ),
        "extra_contribution_yearly": _clamp_int(
            raw["extra_contribution_yearly"], f"phases[{index}].extra_contribution_yearly", 0, 500_000,
        ),
        "withdrawal": _clamp_int(raw["withdrawal"], f"phases[{index}].withdrawal", 0, 500_000),
        "withdrawal_type": withdrawal_type,
        "index_withdrawal": bool(raw["index_withdrawal"]),
    }


def _normalize_scenario(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ScenarioImportError("JSON moet een object zijn met scenario-instellingen.")

    missing = [key for key in REQUIRED_ROOT_KEYS if key not in data]
    if missing:
        raise ScenarioImportError(f"Ontbrekende velden: {', '.join(missing)}.")

    phases_raw = data["phases"]
    if not isinstance(phases_raw, list) or not phases_raw:
        raise ScenarioImportError("Minimaal één fase is verplicht.")

    n_runs = _clamp_int(data["n_runs"], "n_runs", 1, 10_000)
    if n_runs not in VALID_N_RUNS:
        n_runs = min(VALID_N_RUNS, key=lambda v: abs(v - n_runs))

    return {
        "name": str(data["name"]).strip() or "Scenario",
        "tax_mode": str(data["tax_mode"]),
        "fiscaal_partner": bool(data["fiscaal_partner"]),
        "start_capital": _clamp_int(data["start_capital"], "start_capital", 0, 1_000_000_000),
        "goal_label": str(data["goal_label"]),
        "goal_amount": _clamp_int(data["goal_amount"], "goal_amount", 0, 50_000_000),
        "inflation_pct": _clamp_float(data["inflation_pct"], "inflation_pct", 0.0, 10.0),
        "n_runs": n_runs,
        "phases": [_normalize_phase(p, i) for i, p in enumerate(phases_raw)],
    }


def export_scenario_to_json(config_dict: dict) -> str:
    """Zet actuele simulatie-instellingen om naar een nette JSON-string."""
    payload = {
        "schema_version": SCENARIO_SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "name": str(config_dict.get("name", "Scenario")).strip() or "Scenario",
        "tax_mode": str(config_dict.get("tax_mode", "")),
        "fiscaal_partner": bool(config_dict.get("fiscaal_partner", True)),
        "start_capital": int(config_dict.get("start_capital", 0)),
        "goal_label": str(config_dict.get("goal_label", "")),
        "goal_amount": int(config_dict.get("goal_amount", 0)),
        "inflation_pct": float(config_dict.get("inflation_pct", 0.0)),
        "n_runs": int(config_dict.get("n_runs", 10_000)),
        "phases": [
            {
                "id": str(p.get("id", uuid.uuid4().hex[:8])),
                "name": str(p.get("name", f"fase {i + 1}")),
                "years": int(p.get("years", 1)),
                "mu_pct": float(p.get("mu_pct", 0.0)),
                "sigma_pct": float(p.get("sigma_pct", 0.0)),
                "contribution_amount": int(p.get("contribution_amount", 0)),
                "contribution_frequency": str(p.get("contribution_frequency", "maandelijks")),
                "contribution_increase_pct": float(p.get("contribution_increase_pct", 0.0)),
                "extra_contribution_yearly": int(p.get("extra_contribution_yearly", 0)),
                "withdrawal": int(p.get("withdrawal", 0)),
                "withdrawal_type": str(p.get("withdrawal_type", "maandelijks")),
                "index_withdrawal": bool(p.get("index_withdrawal", True)),
            }
            for i, p in enumerate(config_dict.get("phases", []))
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def import_scenario_from_json(json_file: Any) -> dict:
    """Lees en valideer een JSON-bestand; geef genormaliseerde scenario-dict terug."""
    text = _read_json_source(json_file)
    if not text.strip():
        raise ScenarioImportError("Het bestand is leeg.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScenarioImportError(f"Geen geldige JSON: {exc.msg}.") from exc

    return _normalize_scenario(data)


def list_scenarios() -> list[dict]:
    _ensure_dir()
    items: list[dict] = []
    for path in sorted(SCENARIOS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = import_scenario_from_json(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            data["_id"] = path.stem
            items.append(data)
        except (ScenarioImportError, OSError):
            continue
    return items


def save_scenario(payload: dict) -> str:
    _ensure_dir()
    normalized = _normalize_scenario(payload)
    name = normalized["name"]
    normalized["saved_at"] = datetime.now(timezone.utc).isoformat()
    base = _slug(name)
    path = SCENARIOS_DIR / f"{base}.json"
    counter = 2
    while path.exists():
        try:
            existing = import_scenario_from_json(path.read_text(encoding="utf-8"))
            if existing.get("name") == name:
                break
        except ScenarioImportError:
            break
        path = SCENARIOS_DIR / f"{base}-{counter}.json"
        counter += 1
    path.write_text(export_scenario_to_json(normalized), encoding="utf-8")
    return path.stem


def load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' niet gevonden.")
    return import_scenario_from_json(path.read_text(encoding="utf-8"))


def delete_scenario(scenario_id: str) -> None:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if path.exists():
        path.unlink()
