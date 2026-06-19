"""
Streamlit dashboard — Vermogenscalculator (Monte Carlo).
"""

from __future__ import annotations

import re
import uuid
from copy import deepcopy

import numpy as np
import streamlit as st

from chart_builder import SPAGHETTI_RUNS, build_results_chart, phase_x_ranges, x_values, yearly_indices
from scenario_storage import (
    ScenarioImportError,
    delete_scenario,
    export_scenario_to_json,
    import_scenario_from_json,
    list_scenarios,
    load_scenario,
    save_scenario,
)
from simulation_engine import (
    CONTRIBUTION_FREQUENCIES,
    PhaseConfig,
    SimulationConfig,
    compute_percentiles,
    median_run_index,
    run_simulation,
)
from ui_theme import (
    COLORS,
    chart_legend_html,
    format_euro,
    inject_css,
    kpi_card,
    render_explanation,
    render_tax_logic_expander,
)

APP_SUBTITLE = "Monte Carlo simulatie · PfcVassi"

st.set_page_config(
    page_title="Vermogenscalculator",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def safe_download_filename(name: str) -> str:
    """Converteer scenarionaam naar veilige bestandsnaam (bijv. mijn_pensioen_plan.json)."""
    base = name.strip().lower().replace(" ", "_")
    base = re.sub(r"[^\w_-]", "", base).strip("_")
    return f"{base or 'scenario'}.json"


def render_header() -> None:
    st.markdown('<div class="app-header-wrap">', unsafe_allow_html=True)
    with st.container():
        st.markdown("### Vermogenscalculator")
        st.caption(APP_SUBTITLE)
    st.markdown("</div>", unsafe_allow_html=True)

TAX_MODES = (
    "Uit",
    "Huidig stelsel",
    "Nieuw stelsel (onder voorbehoud wetgeving)",
)
X_AXIS_MODES = ("Kalenderjaar", "Simulatiejaar")
WITHDRAWAL_TYPES = ("maandelijks", "jaarlijks")

FREQ_LABELS = {
    "maandelijks": "per maand",
    "kwartaal": "per kwartaal",
    "jaarlijks": "per jaar",
}

WITHDRAWAL_LABELS = {
    "maandelijks": "per maand",
    "jaarlijks": "per jaar",
}

DEFAULT_PHASE = {
    "name": "fase 1",
    "years": 10,
    "mu_pct": 8.0,
    "sigma_pct": 15.0,
    "contribution_amount": 0,
    "contribution_frequency": "maandelijks",
    "contribution_increase_pct": 0.0,
    "extra_contribution_yearly": 0,
    "withdrawal": 0,
    "withdrawal_type": "maandelijks",
    "index_withdrawal": True,
}


def _new_phase(**overrides) -> dict:
    phase = deepcopy(DEFAULT_PHASE)
    phase["id"] = str(uuid.uuid4())[:8]
    phase.update(overrides)
    return phase


def init_session_state() -> None:
    if st.session_state.get("pending_scenario_id"):
        scenario_id = st.session_state.pop("pending_scenario_id")
        try:
            _apply_scenario(load_scenario(scenario_id))
            st.session_state.scenario_import_message = (
                "success",
                f"Scenario '{st.session_state.scenario_name}' geladen.",
            )
        except (ScenarioImportError, FileNotFoundError, OSError) as exc:
            st.session_state.scenario_import_message = ("error", str(exc))
    if st.session_state.get("pending_scenario_upload"):
        raw = st.session_state.pop("pending_scenario_upload")
        try:
            _apply_scenario(import_scenario_from_json(raw))
            st.session_state.scenario_import_message = (
                "success",
                f"Scenario '{st.session_state.scenario_name}' geladen uit JSON.",
            )
        except ScenarioImportError as exc:
            st.session_state.scenario_import_message = ("error", str(exc))
        except Exception as exc:
            st.session_state.scenario_import_message = (
                "error",
                f"Import mislukt: {exc}",
            )
    if "phases" not in st.session_state:
        st.session_state.phases = [_new_phase()]
    st.session_state.setdefault("tax_mode", TAX_MODES[0])
    st.session_state.setdefault("fiscaal_partner", True)
    st.session_state.setdefault("scenario_name", "Basis scenario")
    st.session_state.setdefault("start_capital", 100_000)
    st.session_state.setdefault("goal_label", "Pensioen / nalatenschap")
    st.session_state.setdefault("goal_amount", 500_000)
    st.session_state.setdefault("inflation_pct", 2.0)
    st.session_state.setdefault("n_runs", 10_000)
    st.session_state.setdefault(
        "scenario_naam_download",
        st.session_state.get("scenario_name", "Basis scenario"),
    )


def _scenario_payload() -> dict:
    return {
        "name": st.session_state.scenario_name,
        "tax_mode": st.session_state.tax_mode,
        "fiscaal_partner": st.session_state.fiscaal_partner,
        "start_capital": st.session_state.start_capital,
        "goal_label": st.session_state.goal_label,
        "goal_amount": st.session_state.goal_amount,
        "inflation_pct": st.session_state.inflation_pct,
        "n_runs": st.session_state.n_runs,
        "phases": deepcopy(st.session_state.phases),
    }


def _apply_scenario(data: dict) -> None:
    st.session_state.scenario_name = data.get("name", "Scenario")
    tax = data.get("tax_mode", TAX_MODES[0])
    st.session_state.tax_mode = tax if tax in TAX_MODES else TAX_MODES[0]
    st.session_state.fiscaal_partner = bool(data.get("fiscaal_partner", True))
    st.session_state.start_capital = int(data.get("start_capital", 100_000))
    st.session_state.goal_label = str(data.get("goal_label", ""))
    st.session_state.goal_amount = int(data.get("goal_amount", 0))
    st.session_state.inflation_pct = float(data.get("inflation_pct", 2.0))
    st.session_state.n_runs = int(data.get("n_runs", 10_000))
    phases = deepcopy(data.get("phases", [_new_phase()]))
    for phase in phases:
        phase.setdefault("id", str(uuid.uuid4())[:8])
    st.session_state.phases = phases


def render_scenario_panel() -> None:
    with st.expander("Scenario's opslaan & laden"):
        msg = st.session_state.pop("scenario_import_message", None)
        if msg:
            level, text = msg
            if level == "success":
                st.success(text)
            else:
                st.error(text)

        st.markdown("**Permanent bewaren op je eigen computer**")
        scenario_naam_input = st.text_input(
            "Naam van dit scenario voor het bestand:",
            key="scenario_naam_download",
        )
        st.download_button(
            label="💾 Sla scenario op als bestand",
            data=export_scenario_to_json(_scenario_payload()),
            file_name=safe_download_filename(scenario_naam_input),
            mime="application/json",
            type="primary",
            use_container_width=True,
        )
        uploaded = st.file_uploader(
            "Laad een eerder opgeslagen bestand",
            type=["json"],
            key="scenario_json_uploader",
        )
        st.caption("Je data blijft 100% van jou. Er wordt niets op een centrale server opgeslagen.")
        if uploaded is not None and st.button(
            "Importeer JSON-bestand",
            key="import_json_btn",
            use_container_width=True,
        ):
            st.session_state.pending_scenario_upload = uploaded.getvalue()
            st.rerun()

        st.divider()
        st.markdown("**Tijdelijk opslaan (blijft hooguit enkele dagen behouden)**")
        st.caption("Opgeslagen in `.scenarios/` (niet in git).")

        if st.button("Snel opslaan voor deze sessie", type="primary", use_container_width=True):
            try:
                save_scenario(_scenario_payload())
                st.success(f"Scenario '{st.session_state.scenario_name}' opgeslagen.")
            except OSError as exc:
                st.error(f"Opslaan mislukt: {exc}")

        saved = list_scenarios()
        if not saved:
            st.info("Nog geen opgeslagen scenario's.")
            return

        st.markdown("**Opgeslagen scenario's**")
        for item in saved:
            saved_at = item.get("saved_at", "")[:10]
            label = f"{item['name']} ({saved_at})" if saved_at else item["name"]
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(label)
            with c2:
                if st.button("Laden", key=f"load_{item['_id']}", use_container_width=True):
                    st.session_state.pending_scenario_id = item["_id"]
                    st.rerun()
            with c3:
                if st.button("Verwijder", key=f"del_{item['_id']}", use_container_width=True):
                    delete_scenario(item["_id"])
                    st.rerun()


def _yearly_indices(n_months: int) -> np.ndarray:
    return yearly_indices(n_months)


def success_rate_goal(end_values: np.ndarray, goal: float) -> tuple[float, int]:
    ok = end_values >= goal
    count = int(np.sum(ok))
    return float(count / end_values.shape[0] * 100), count


def format_success_rate(rate: float, count: int, n_runs: int) -> str:
    if count == n_runs:
        return "100%"
    if count == 0:
        return "0%"
    return f"{rate:.1f}%"


def _sample_spaghetti(paths: np.ndarray, year_idx: np.ndarray, n_samples: int) -> np.ndarray:
    n_runs = paths.shape[0]
    indices = np.arange(n_runs) if n_runs <= n_samples else np.linspace(0, n_runs - 1, n_samples, dtype=int)
    return paths[indices][:, year_idx]


def phases_to_config(
    n_runs: int,
    start_capital: int,
    inflation_pct: float,
    phase_dicts: list[dict],
    fiscaal_partner: bool,
) -> SimulationConfig:
    phases = tuple(
        PhaseConfig(
            name=p["name"],
            years=int(p["years"]),
            mu=float(p["mu_pct"]) / 100.0,
            sigma=float(p["sigma_pct"]) / 100.0,
            contribution_amount=int(p["contribution_amount"]),
            contribution_frequency=p["contribution_frequency"],
            contribution_increase=float(p["contribution_increase_pct"]) / 100.0,
            extra_contribution_yearly=int(p["extra_contribution_yearly"]),
            withdrawal=int(p["withdrawal"]),
            withdrawal_monthly=p["withdrawal_type"] == "maandelijks",
            index_withdrawal=bool(p["index_withdrawal"]),
        )
        for p in phase_dicts
    )
    return SimulationConfig(
        n_runs=int(n_runs),
        start_capital=float(start_capital),
        inflation_rate=float(inflation_pct) / 100.0,
        phases=phases,
        fiscaal_partner=bool(fiscaal_partner),
    )


@st.cache_data(show_spinner=False)
def cached_simulation(config: SimulationConfig) -> dict:
    sim = run_simulation(config)
    p10_h, p50_h, p90_h = compute_percentiles(sim.paths_huidig)
    p10_n, p50_n, p90_n = compute_percentiles(sim.paths_nieuw)
    p10_z, p50_z, p90_z = compute_percentiles(sim.paths_zonder_belasting)
    idx_h, idx_n = median_run_index(sim.paths_huidig), median_run_index(sim.paths_nieuw)
    year_idx = _yearly_indices(len(sim.timestamps))

    return {
        "timestamps": sim.timestamps,
        "spaghetti_huidig": _sample_spaghetti(sim.paths_huidig, year_idx, SPAGHETTI_RUNS),
        "spaghetti_nieuw": _sample_spaghetti(sim.paths_nieuw, year_idx, SPAGHETTI_RUNS),
        "spaghetti_zonder": _sample_spaghetti(sim.paths_zonder_belasting, year_idx, SPAGHETTI_RUNS),
        "end_huidig": sim.paths_huidig[:, -1],
        "end_nieuw": sim.paths_nieuw[:, -1],
        "end_zonder": sim.paths_zonder_belasting[:, -1],
        "p10_huidig": p10_h, "p50_huidig": p50_h, "p90_huidig": p90_h,
        "p10_nieuw": p10_n, "p50_nieuw": p50_n, "p90_nieuw": p90_n,
        "p10_zonder": p10_z, "p50_zonder": p50_z, "p90_zonder": p90_z,
        "cumulative_contributions": sim.cumulative_contributions,
        "cumulative_withdrawals": sim.cumulative_withdrawals,
        "tax_huidig_median": float(sim.cumulative_tax_huidig[idx_h, -1]),
        "tax_nieuw_median": float(sim.cumulative_tax_nieuw[idx_n, -1]),
        "total_ingelegd": float(sim.cumulative_contributions[-1]),
        "total_opgenomen": float(sim.cumulative_withdrawals[-1]),
        "start_capital": config.start_capital,
        "n_months": len(sim.timestamps),
        "start_year": config.simulation_start_year,
        "horizon_years": config.horizon_years,
    }


def _paths_for_tax_mode(result: dict, tax_mode: str):
    if tax_mode.startswith("Nieuw"):
        return (
            result["p10_nieuw"], result["p50_nieuw"], result["p90_nieuw"],
            result["spaghetti_nieuw"], result["tax_nieuw_median"],
            result["end_nieuw"],
        )
    if tax_mode.startswith("Huidig"):
        return (
            result["p10_huidig"], result["p50_huidig"], result["p90_huidig"],
            result["spaghetti_huidig"], result["tax_huidig_median"],
            result["end_huidig"],
        )
    return (
        result["p10_zonder"], result["p50_zonder"], result["p90_zonder"],
        result["spaghetti_zonder"], 0.0,
        result["end_zonder"],
    )


def build_chart(
    result: dict,
    config: SimulationConfig,
    tax_mode: str,
    x_mode: str,
    goal_amount: float,
):
    year_idx = _yearly_indices(result["n_months"])
    x_vals = x_values(result["start_year"], x_mode, year_idx)
    x_title = "Simulatiejaar" if x_mode == "Simulatiejaar" else "Kalenderjaar"
    p10, p50, p90, spaghetti, _, _ = _paths_for_tax_mode(result, tax_mode)
    p10_y = np.round(p10[year_idx])
    p50_y = np.round(p50[year_idx])
    p90_y = np.round(p90[year_idx])
    return build_results_chart(
        x_vals=x_vals,
        p10_y=p10_y,
        p50_y=p50_y,
        p90_y=p90_y,
        spaghetti=spaghetti,
        phase_ranges=phase_x_ranges(config, result["start_year"], x_mode),
        goal_amount=goal_amount,
        x_title=x_title,
    )


def render_phase_editor(index: int, phase: dict, total: int) -> None:
    pid = phase["id"]
    label = f"Fase {index + 1}: {phase['name']}"

    with st.expander(label, expanded=(index == total - 1)):
        if total > 1:
            row1 = st.columns([5, 0.4, 0.4, 0.4], gap="small")
            with row1[0]:
                phase["name"] = st.text_input("Naam", phase["name"], key=f"nm_{pid}")
            with row1[1]:
                if st.button("↑", key=f"up_{pid}", disabled=index == 0, use_container_width=True):
                    st.session_state.phases[index], st.session_state.phases[index - 1] = (
                        st.session_state.phases[index - 1], st.session_state.phases[index],
                    )
                    st.rerun()
            with row1[2]:
                if st.button("↓", key=f"dn_{pid}", disabled=index == total - 1, use_container_width=True):
                    st.session_state.phases[index], st.session_state.phases[index + 1] = (
                        st.session_state.phases[index + 1], st.session_state.phases[index],
                    )
                    st.rerun()
            with row1[3]:
                if st.button("✕", key=f"del_{pid}", use_container_width=True):
                    st.session_state.phases.pop(index)
                    st.rerun()
        else:
            phase["name"] = st.text_input("Naam", phase["name"], key=f"nm_{pid}")

        phase["years"] = st.slider("Looptijd (jaren)", 1, 50, int(phase["years"]), key=f"y_{pid}")
        c1, c2 = st.columns(2)
        with c1:
            phase["mu_pct"] = st.slider("Rendement (%)", 0.0, 25.0, float(phase["mu_pct"]), 0.5, key=f"mu_{pid}")
        with c2:
            phase["sigma_pct"] = st.slider("Volatiliteit (%)", 0.0, 50.0, float(phase["sigma_pct"]), 0.5, key=f"sg_{pid}")

        f1, f2 = st.columns(2)
        with f1:
            phase["contribution_frequency"] = st.selectbox(
                "Frequentie inleg",
                CONTRIBUTION_FREQUENCIES,
                index=CONTRIBUTION_FREQUENCIES.index(phase.get("contribution_frequency", "maandelijks")),
                key=f"cf_{pid}",
            )
        with f2:
            freq_lbl = FREQ_LABELS[phase["contribution_frequency"]]
            phase["contribution_amount"] = st.number_input(
                f"Inleg (€ {freq_lbl})",
                min_value=0, max_value=500_000,
                value=int(phase["contribution_amount"]), step=50,
                format="%d", key=f"ca_{pid}_{phase['contribution_frequency']}",
            )

        phase["contribution_increase_pct"] = st.slider(
            "Inlegverhoging per jaar (%)", 0.0, 15.0, float(phase["contribution_increase_pct"]), 0.5, key=f"ci_{pid}",
        )

        phase["extra_contribution_yearly"] = st.number_input(
            "Extra inleg/jaar (€)", 0, 500_000, int(phase["extra_contribution_yearly"]), 500,
            format="%d", key=f"ex_{pid}",
        )

        w1, w2 = st.columns(2)
        with w1:
            phase["withdrawal_type"] = st.selectbox(
                "Type opname",
                WITHDRAWAL_TYPES,
                index=WITHDRAWAL_TYPES.index(phase.get("withdrawal_type", "maandelijks")),
                key=f"wt_{pid}",
            )
        with w2:
            wd_lbl = WITHDRAWAL_LABELS[phase["withdrawal_type"]]
            phase["withdrawal"] = st.number_input(
                f"Opname (€ {wd_lbl})",
                0, 500_000, int(phase["withdrawal"]), 500,
                format="%d", key=f"wd_{pid}_{phase['withdrawal_type']}",
            )

        phase["index_withdrawal"] = st.toggle(
            "Indexeer opname met inflatie",
            value=bool(phase.get("index_withdrawal", True)),
            key=f"ix_{pid}",
        )


def main() -> None:
    try:
        inject_css()
        init_session_state()
        render_header()

        plan_col, main_col = st.columns([1, 2.3], gap="medium")

        with plan_col:
            st.markdown('<div class="plan-col-marker"></div>', unsafe_allow_html=True)
            st.markdown('<p class="section-label">Planning</p>', unsafe_allow_html=True)

            with st.expander("Algemeen", expanded=True):
                st.caption("Box 3 belasting")
                tax_mode = st.radio(
                    "Box 3 belasting",
                    TAX_MODES,
                    horizontal=True,
                    label_visibility="collapsed",
                    key="tax_mode",
                )
                fiscaal_partner = st.toggle("Fiscaal partner", key="fiscaal_partner")
                scenario_name = st.text_input("Scenario", key="scenario_name")
                start_capital = st.number_input(
                    "Startkapitaal (€)", 0, 1_000_000_000, step=1_000, format="%d",
                    key="start_capital",
                )
                goal_label = st.text_input(
                    "Doel (optioneel)",
                    help="Vrij veld: bijv. pensioen, nalatenschap, studie kinderen.",
                    key="goal_label",
                )
                goal_amount = st.number_input(
                    "Streefbedrag einddatum (€)",
                    min_value=0,
                    max_value=50_000_000,
                    step=10_000,
                    format="%d",
                    help="Slagingskans = % runs waarbij je eindvermogen dit bedrag haalt of overschrijdt.",
                    key="goal_amount",
                )
                inflation_pct = st.slider("Inflatie (%)", 0.0, 10.0, step=0.5, key="inflation_pct")
                n_runs = st.select_slider("Runs", [1_000, 2_500, 5_000, 10_000], key="n_runs")

            horizon = sum(int(p["years"]) for p in st.session_state.phases)
            st.caption(f"Horizon: **{horizon} jaar** · {len(st.session_state.phases)} fase(s)")

            st.markdown('<p class="section-label">Fasen</p>', unsafe_allow_html=True)
            for i, phase in enumerate(list(st.session_state.phases)):
                render_phase_editor(i, phase, len(st.session_state.phases))

            if st.button("➕ Fase toevoegen", type="primary", use_container_width=True):
                st.session_state.phases.append(_new_phase(name=f"fase {len(st.session_state.phases) + 1}"))
                st.rerun()

        config = phases_to_config(
            n_runs, start_capital, inflation_pct, st.session_state.phases, fiscaal_partner,
        )

        with st.spinner("Berekenen…"):
            result = cached_simulation(config)

        p10, p50, p90, _, total_tax, end_values = _paths_for_tax_mode(result, tax_mode)
        slagingskans, success_count = success_rate_goal(end_values, float(goal_amount))
        end_value = float(p50[-1])
        rendement = (
            end_value - config.start_capital
            - result["total_ingelegd"] + result["total_opgenomen"] + total_tax
        )
        goal_short = goal_label.strip() or "streefbedrag"

        with main_col:
            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                st.markdown(kpi_card("Ingelegd", format_euro(result["total_ingelegd"])), unsafe_allow_html=True)
            with k2:
                st.markdown(kpi_card("Opgenomen", format_euro(result["total_opgenomen"])), unsafe_allow_html=True)
            with k3:
                st.markdown(kpi_card("Rendement", format_euro(rendement), "positive" if rendement >= 0 else "negative"), unsafe_allow_html=True)
            with k4:
                st.markdown(kpi_card("Box 3", format_euro(-total_tax), "negative"), unsafe_allow_html=True)
            with k5:
                st.markdown(
                    kpi_card("Eindwaarde P50", format_euro(end_value), "positive" if end_value >= 0 else "negative"),
                    unsafe_allow_html=True,
                )

            with st.container(border=True):
                h1, h2 = st.columns([3, 1])
                with h1:
                    st.markdown("**Resultaten**")
                    st.markdown(chart_legend_html(), unsafe_allow_html=True)
                with h2:
                    x_mode = st.radio("X-as", X_AXIS_MODES, horizontal=True, label_visibility="collapsed")

                fig, chart_note = build_chart(result, config, tax_mode, x_mode, float(goal_amount))
                st.plotly_chart(fig, use_container_width=True)
                if chart_note:
                    st.caption(chart_note)

                rate_text = format_success_rate(slagingskans, success_count, config.n_runs)
                st.markdown(
                    f'<div class="success-rate">'
                    f'<span style="color:{COLORS["muted"]};font-size:0.82rem">'
                    f'Slagingskans ({goal_short} ≥ {format_euro(goal_amount, compact=False)})</span>'
                    f'<div class="success-rate-value">{rate_text}</div>'
                    f'<span style="color:{COLORS["muted"]};font-size:0.78rem">'
                    f'{success_count:,} van {config.n_runs:,} runs halen het streefbedrag</span></div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{result['start_year']}–{result['start_year'] + config.horizon_years - 1} · "
                    f"P10 {format_euro(p10[-1])} · P50 {format_euro(p50[-1])} · P90 {format_euro(p90[-1])}"
                )

            render_explanation(
                config.horizon_years, result["total_ingelegd"], result["total_opgenomen"],
                rendement, total_tax, end_value, config.start_capital, config.n_runs,
                float(goal_amount), goal_label,
            )
            render_tax_logic_expander(config, tax_mode)
            render_scenario_panel()
    except Exception as exc:
        st.error("De app kon niet volledig laden. Controleer je invoer of herstart de pagina.")
        st.exception(exc)


if __name__ == "__main__":
    main()
