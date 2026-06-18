"""
Monte Carlo simulatie voor vermogensopbouw.
CLI-entrypoint; kernlogica staat in simulation_engine.py.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import WriteOptions

from influx_config import (
    INFLUX_BATCH_PAUSE_S,
    INFLUX_BATCH_SIZE,
    INFLUX_BUCKET,
    INFLUX_FLUSH_INTERVAL_MS,
    INFLUX_ORG,
    INFLUX_URL,
    get_influx_token,
    influx_export_available,
)
from simulation_engine import SimulationConfig, compute_percentiles, run_simulation

MEASUREMENT_NAME = "vermogen_monte_carlo"
SCENARIO_TAG = "basis_scenario"

DEFAULT_CONFIG = SimulationConfig()


def print_summary(
    paths_huidig,
    paths_nieuw,
    config: SimulationConfig,
    timestamps: list[datetime],
) -> None:
    start_year = config.simulation_start_year
    end_year = config.simulation_start_year + config.simulation_end_year
    print(f"Periode: {start_year} t/m {end_year} ({len(timestamps)} maanden, {config.horizon_years} jaar)")

    for label, paths in (("Huidig stelsel", paths_huidig), ("Nieuw stelsel", paths_nieuw)):
        p10, p50, p90 = compute_percentiles(paths)
        print(f"\n=== {label} ===")
        print(f"  Eindvermogen P10: €{p10[-1]:,.0f}")
        print(f"  Eindvermogen P50: €{p50[-1]:,.0f}")
        print(f"  Eindvermogen P90: €{p90[-1]:,.0f}")


def write_to_influx(
    timestamps: list[datetime],
    p10_huidig,
    p50_huidig,
    p90_huidig,
    p10_nieuw,
    p50_nieuw,
    p90_nieuw,
    scenario_tag: str = SCENARIO_TAG,
) -> None:
    """Schrijf percentielen naar InfluxDB2 in batches."""
    token = get_influx_token()
    if not token:
        raise RuntimeError(
            "INFLUX_TOKEN ontbreekt. Stel in via Streamlit secrets of omgevingsvariabele INFLUX_TOKEN."
        )

    points = [
        Point(MEASUREMENT_NAME)
        .tag("scenario", scenario_tag)
        .field("p10_huidig", float(p10_huidig[i]))
        .field("p50_huidig", float(p50_huidig[i]))
        .field("p90_huidig", float(p90_huidig[i]))
        .field("p10_nieuw", float(p10_nieuw[i]))
        .field("p50_nieuw", float(p50_nieuw[i]))
        .field("p90_nieuw", float(p90_nieuw[i]))
        .time(ts)
        for i, ts in enumerate(timestamps)
    ]

    write_options = WriteOptions(
        batch_size=INFLUX_BATCH_SIZE,
        flush_interval=INFLUX_FLUSH_INTERVAL_MS,
    )

    with InfluxDBClient(url=INFLUX_URL, token=token, org=INFLUX_ORG) as client:
        write_api = client.write_api(write_options=write_options)
        n_batches = 0
        for i in range(0, len(points), INFLUX_BATCH_SIZE):
            batch = points[i : i + INFLUX_BATCH_SIZE]
            write_api.write(bucket=INFLUX_BUCKET, record=batch)
            n_batches += 1
            if i + INFLUX_BATCH_SIZE < len(points):
                time.sleep(INFLUX_BATCH_PAUSE_S)
        write_api.flush()

    print(
        f"Geschreven: {len(points)} datapunten in {n_batches} batches "
        f"naar bucket '{INFLUX_BUCKET}'."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulatie vermogensopbouw met export naar InfluxDB2.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Voer simulatie uit en print samenvatting, zonder naar InfluxDB te schrijven.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = DEFAULT_CONFIG

    print(
        f"Start simulatie: {config.n_runs:,} runs, "
        f"{config.horizon_years} jaar ({len(config.phases)} fasen) ..."
    )
    sim = run_simulation(config)
    paths_huidig, paths_nieuw, timestamps = sim.paths_huidig, sim.paths_nieuw, sim.timestamps

    p10_huidig, p50_huidig, p90_huidig = compute_percentiles(paths_huidig)
    p10_nieuw, p50_nieuw, p90_nieuw = compute_percentiles(paths_nieuw)

    print_summary(paths_huidig, paths_nieuw, config, timestamps)

    if args.dry_run:
        print("\nDry-run: geen data geschreven naar InfluxDB.")
    elif not influx_export_available():
        print(
            "\nINFLUX_TOKEN ontbreekt — export overgeslagen. "
            "Stel INFLUX_TOKEN in via omgevingsvariabele of gebruik --dry-run."
        )
    else:
        write_to_influx(
            timestamps,
            p10_huidig, p50_huidig, p90_huidig,
            p10_nieuw, p50_nieuw, p90_nieuw,
        )


if __name__ == "__main__":
    main()
