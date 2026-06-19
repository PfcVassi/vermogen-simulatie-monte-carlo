"""Gedeelde UI-styling voor het Streamlit-dashboard."""

from __future__ import annotations

import streamlit as st

COLORS = {
    "bg": "#f4f6f9",
    "card": "#ffffff",
    "primary": "#1e40af",
    "text": "#0f172a",
    "muted": "#64748b",
    "border": "#e2e8f0",
    "green": "#15803d",
    "green_bg": "#f0fdf4",
    "red": "#b91c1c",
    "red_bg": "#fef2f2",
    "warning_bg": "#fff7ed",
    "warning_border": "#fed7aa",
    "spaghetti": "rgba(100, 116, 139, 0.14)",
    "goal": "#7c3aed",
}

CHART = {
    "p10": "#2563eb",
    "p50": "#0f172a",
    "p90": "#16a34a",
    "band_fill": "rgba(219, 39, 119, 0.18)",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
        .stApp {{ background: {COLORS["bg"]}; }}
        #MainMenu, footer, header {{ visibility: hidden; }}
        .block-container {{ padding-top: 0.5rem; max-width: 1480px; }}

        .app-header-wrap {{
            background: #ffffff;
            border: 1px solid {COLORS["border"]};
            border-radius: 0 0 14px 14px;
            margin-bottom: 1.1rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        }}

        .app-header-wrap [data-testid="stVerticalBlockBorderWrapper"] {{
            border: none !important;
            box-shadow: none !important;
            background: transparent !important;
        }}

        .app-header-wrap [data-testid="stImage"] {{
            display: none !important;
        }}

        .section-label {{
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            color: {COLORS["muted"]};
            margin: 0.5rem 0 0.35rem 0;
        }}

        /* Linker planningskolom: vaste breedte, inputs niet uitgerekt */
        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child {{
            flex: 0 0 22rem !important;
            min-width: 22rem;
            max-width: 22rem;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stNumberInput"] > div:last-child {{
            width: 100% !important;
            max-width: 100% !important;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stNumberInput"] input {{
            min-width: 0;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stRadio"] [role="radiogroup"] {{
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 0.25rem !important;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stRadio"] label {{
            font-size: 0.74rem !important;
            padding: 0.26rem 0.4rem !important;
            white-space: nowrap;
            flex: 1 1 auto;
            text-align: center;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stRadio"] label p {{
            font-size: 0.74rem !important;
        }}

        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stExpander"] [data-testid="column"]:nth-child(2) .stButton > button,
        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stExpander"] [data-testid="column"]:nth-child(3) .stButton > button,
        [data-testid="stHorizontalBlock"]:has(.plan-col-marker) > [data-testid="column"]:first-child
        [data-testid="stExpander"] [data-testid="column"]:nth-child(4) .stButton > button {{
            min-height: 2.1rem;
            padding: 0.15rem 0.25rem;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: {COLORS["card"]};
            border-color: {COLORS["border"]} !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }}

        div[data-testid="stExpander"] {{
            border: 1px solid {COLORS["border"]} !important;
            border-radius: 12px !important;
            margin-bottom: 0.45rem;
            background: {COLORS["card"]};
        }}

        .kpi-card {{
            background: {COLORS["card"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 0.85rem 0.95rem;
            min-height: 78px;
        }}

        .kpi-label {{ font-size: 0.76rem; color: {COLORS["muted"]}; font-weight: 500; }}
        .kpi-value {{ font-size: 1.22rem; font-weight: 700; }}

        .chart-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem 1.1rem;
            margin: 0.1rem 0 0.45rem 0;
            font-size: 0.8rem;
            color: {COLORS["text"]};
            line-height: 1.4;
        }}

        .legend-item {{ display: inline-flex; align-items: center; gap: 0.4rem; }}
        .legend-swatch {{ width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; }}
        .legend-muted {{ color: {COLORS["muted"]}; font-size: 0.76rem; }}

        .success-rate {{ text-align: center; margin: 0.35rem 0 0.15rem 0; }}
        .success-rate-value {{ font-size: 1.35rem; font-weight: 700; }}

        .stButton > button[kind="primary"] {{
            background: {COLORS["primary"]} !important;
            border-color: {COLORS["primary"]} !important;
            color: #ffffff !important;
        }}

        .stDownloadButton > button,
        [data-testid="stDownloadButton"] button {{
            background: {COLORS["primary"]} !important;
            border-color: {COLORS["primary"]} !important;
            color: #ffffff !important;
        }}

        .stDownloadButton > button:hover,
        [data-testid="stDownloadButton"] button:hover {{
            background: #1e3a8a !important;
            border-color: #1e3a8a !important;
            color: #ffffff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, tone: str = "neutral", subtitle: str = "") -> str:
    value_color = COLORS["text"]
    bg = COLORS["card"]
    if tone == "positive":
        value_color, bg = COLORS["green"], COLORS["green_bg"]
    elif tone == "negative":
        value_color, bg = COLORS["red"], COLORS["red_bg"]
    sub = (
        f'<div style="font-size:0.72rem;color:{COLORS["muted"]};margin-top:0.2rem">{subtitle}</div>'
        if subtitle else ""
    )
    return f"""
    <div class="kpi-card" style="background:{bg}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{value_color}">{value}</div>{sub}
    </div>
    """


def format_euro(value: float, compact: bool = True) -> str:
    rounded = int(round(value))
    sign = "-" if rounded < 0 else ""
    abs_val = abs(rounded)
    if not compact:
        return f"{sign}€{abs_val:,}".replace(",", ".")

    if abs_val >= 1_000_000:
        mln = abs_val / 1_000_000
        return f"{sign}€{mln:.1f}".replace(".", ",") + " mln"

    if abs_val >= 10_000:
        k = abs_val / 1_000
        if abs_val % 1_000 == 0:
            return f"{sign}€{int(k)}K"
        return f"{sign}€{k:.1f}".replace(".", ",") + "K"

    return f"{sign}€{abs_val:,}".replace(",", ".")


def chart_legend_html() -> str:
    return f"""
    <div class="chart-legend">
        <span class="legend-item">
            <span class="legend-swatch" style="background:{CHART["band_fill"]};border:1px solid #db2777"></span>
            <span><strong>Band</strong> <span class="legend-muted">— P10 t/m P90 (volledige spreiding)</span></span>
        </span>
        <span class="legend-item">
            <span class="legend-swatch" style="background:{CHART["p50"]}"></span>
            <span><strong>P50</strong> <span class="legend-muted">— mediaan vermogen</span></span>
        </span>
        <span class="legend-item">
            <span class="legend-swatch" style="background:transparent;border:2px dashed {CHART["p10"]}"></span>
            <span><strong>P10 / P90</strong> <span class="legend-muted">— gestippeld</span></span>
        </span>
        <span class="legend-item">
            <span class="legend-swatch" style="background:{COLORS["goal"]}"></span>
            <span class="legend-muted">Streefbedrag · stippellijn = €0</span>
        </span>
    </div>
    """


def render_explanation(
    horizon: int,
    ingelegd: float,
    opgenomen: float,
    rendement: float,
    belasting: float,
    eindwaarde: float,
    startkapitaal: float,
    n_runs: int,
    goal_amount: float,
    goal_label: str,
) -> None:
    with st.container(border=True):
        st.markdown("**Toelichting resultaten**")

        if eindwaarde < 0:
            st.warning(
                f"Negatieve eindwaarde: je hebt structureel meer opgenomen dan het vermogen "
                f"kon dragen. Mediaan eindwaarde: {format_euro(eindwaarde, compact=False)}."
            )

        goal_txt = goal_label.strip() or "streefbedrag"
        st.markdown(
            f"Over **{horizon} jaar** (som van je fasen, mediaan-scenario) leg je "
            f"**{format_euro(ingelegd, compact=False)}** in, neem je "
            f"**{format_euro(opgenomen, compact=False)}** op, en is het marktrendement (bruto) "
            f"**{format_euro(rendement, compact=False)}** "
            f"(Box 3: **{format_euro(belasting, compact=False)}**). "
            f"Je {goal_txt} is **{format_euro(goal_amount, compact=False)}** aan het einde van de looptijd."
        )

        formula = (
            f"{format_euro(startkapitaal, compact=False)} startkapitaal"
            f" + {format_euro(ingelegd, compact=False)} ingelegd"
            f" - {format_euro(opgenomen, compact=False)} opgenomen"
            f" + {format_euro(rendement, compact=False)} rendement"
            f" - {format_euro(belasting, compact=False)} belasting"
            f" = {format_euro(eindwaarde, compact=False)} eindwaarde (P50)"
        )
        st.info(formula)

        st.caption(
            f"Slagingskans = % runs waarbij eindvermogen ≥ streefbedrag ({format_euro(goal_amount, compact=False)}). "
            f"P10/P50/P90 = percentielen uit {n_runs:,} simulaties. Geen financieel advies."
        )


def render_tax_logic_expander(config, tax_mode: str) -> None:
    from simulation_engine import describe_tax_logic

    with st.expander("Bekijk de toegepaste belasting-logica"):
        st.markdown(describe_tax_logic(config, tax_mode))
