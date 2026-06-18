"""InfluxDB-configuratie via Streamlit Secrets of omgevingsvariabelen."""

from __future__ import annotations

import os


def get_influx_token() -> str | None:
    """Token uit Streamlit secrets (cloud) of INFLUX_TOKEN env-var (CLI/lokaal)."""
    try:
        import streamlit as st

        token = st.secrets.get("INFLUX_TOKEN", None)
        if token:
            return str(token)
    except Exception:
        pass
    env = os.getenv("INFLUX_TOKEN")
    return env if env else None


def influx_export_available() -> bool:
    return get_influx_token() is not None


def _influx_setting(key: str, default: str = "") -> str:
    try:
        import streamlit as st

        value = st.secrets.get(key, None)
        if value is not None and str(value):
            return str(value)
    except Exception:
        pass
    return os.getenv(key, default)


INFLUX_URL = _influx_setting("INFLUX_URL", "http://localhost:8086")
INFLUX_ORG = _influx_setting("INFLUX_ORG", "")
INFLUX_BUCKET = _influx_setting("INFLUX_BUCKET", "monte_carlo")
INFLUX_BATCH_SIZE = int(_influx_setting("INFLUX_BATCH_SIZE", "50"))
INFLUX_FLUSH_INTERVAL_MS = int(_influx_setting("INFLUX_FLUSH_INTERVAL_MS", "1000"))
INFLUX_BATCH_PAUSE_S = float(_influx_setting("INFLUX_BATCH_PAUSE_S", "0.1"))
