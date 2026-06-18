"""Plotly-grafiek voor Monte Carlo resultaten."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from simulation_engine import SimulationConfig
from ui_theme import CHART, COLORS, format_euro

PHASE_TINTS = ("#3b82f6", "#eab308", "#22c55e", "#a855f7", "#f97316")
SPAGHETTI_RUNS = 12
LOG_SCALE_RATIO_THRESHOLD = 12.0


def yearly_indices(n_months: int) -> np.ndarray:
    return np.arange(11, n_months, 12)


def x_values(start_year: int, x_mode: str, year_idx: np.ndarray) -> np.ndarray:
    years = year_idx // 12
    return start_year + years if x_mode == "Kalenderjaar" else years


def phase_x_ranges(config: SimulationConfig, start_year: int, x_mode: str) -> list[tuple[float, float, str]]:
    ranges: list[tuple[float, float, str]] = []
    cumulative = 0
    for phase in config.phases:
        start = cumulative
        cumulative += phase.years
        if x_mode == "Kalenderjaar":
            ranges.append((start_year + start, start_year + cumulative, phase.name))
        else:
            ranges.append((float(start), float(cumulative), phase.name))
    return ranges


def chart_axis(
    p10_y: np.ndarray,
    p50_y: np.ndarray,
    p90_y: np.ndarray,
    goal_amount: float,
) -> tuple[float | None, float | None, bool, str | None]:
    """
    Y-as altijd op volledige P10–P90-band (nooit inkorten t.o.v. mediaan).
    Bij grote ratio's (typisch hoge volatiliteit): log-schaal zodat de band leesbaar blijft.
    """
    band_lo = float(np.min(p10_y))
    band_hi = float(np.max(p90_y))
    y_min = band_lo
    y_max = band_hi

    if goal_amount != 0:
        y_min = min(y_min, goal_amount)
        y_max = max(y_max, goal_amount)

    span = max(y_max - y_min, 1.0)
    pad = max(span * 0.06, abs(y_max) * 0.02, 1_000)
    y_min -= pad
    y_max += pad

    all_positive = band_lo > 0 and float(np.min(p50_y)) > 0
    max_ratio = band_hi / max(band_lo, 1.0)
    end_ratio = float(p90_y[-1]) / max(float(p10_y[-1]), 1.0)
    use_log = all_positive and (
        max_ratio >= LOG_SCALE_RATIO_THRESHOLD or end_ratio >= LOG_SCALE_RATIO_THRESHOLD
    )

    scale_note = None
    if use_log:
        scale_note = (
            "Logaritmische Y-as: volledige P10–P90-band zichtbaar. "
            "Hogere volatiliteit = bredere spreiding (grotere verhouding P90/P10)."
        )
        return None, None, True, scale_note

    if band_lo >= 0 and float(np.min(p50_y)) >= 0 and y_min < 0 and band_lo > pad * 2:
        y_min = 0.0

    return y_min, y_max, False, scale_note


def build_results_chart(
    x_vals: np.ndarray,
    p10_y: np.ndarray,
    p50_y: np.ndarray,
    p90_y: np.ndarray,
    spaghetti: np.ndarray | None,
    phase_ranges: list[tuple[float, float, str]],
    goal_amount: float,
    x_title: str,
) -> tuple[go.Figure, str | None]:
    y_min, y_max, use_log, scale_note = chart_axis(p10_y, p50_y, p90_y, goal_amount)

    footnote = scale_note
    if spaghetti is not None and spaghetti.size:
        if use_log:
            clipped = float(np.max(spaghetti)) > float(np.max(p90_y)) * 3
        else:
            clipped = float(np.max(spaghetti)) > (y_max or 0)
        if clipped:
            extra = " Losse scenario-uitschieters vallen buiten beeld."
            footnote = (footnote or "") + extra

    fig = go.Figure()

    for i, (x0, x1, name) in enumerate(phase_ranges):
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor=PHASE_TINTS[i % len(PHASE_TINTS)],
            opacity=0.07,
            layer="below",
            line_width=0,
        )
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=1.06,
            yref="paper",
            text=name,
            showarrow=False,
            font=dict(size=10, color=COLORS["muted"]),
        )

    if not use_log and y_min is not None and y_max is not None and y_min < 0 < y_max:
        fig.add_hline(y=0, line_width=1, line_color="#94a3b8", line_dash="dot")

    if spaghetti is not None:
        for i in range(spaghetti.shape[0]):
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=np.round(spaghetti[i]),
                mode="lines",
                line=dict(color=COLORS["spaghetti"], width=0.8),
                showlegend=False,
                hoverinfo="skip",
                cliponaxis=True,
            ))

    fig.add_trace(go.Scatter(
        x=np.concatenate([x_vals, x_vals[::-1]]),
        y=np.concatenate([p90_y, p10_y[::-1]]),
        fill="toself",
        fillcolor=CHART["band_fill"],
        line=dict(width=0),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=x_vals, y=p10_y, mode="lines", name="P10",
        line=dict(color=CHART["p10"], width=1.8, dash="dash"),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x_vals, y=p90_y, mode="lines", name="P90",
        line=dict(color=CHART["p90"], width=1.8, dash="dash"),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x_vals, y=p50_y, mode="lines", name="P50",
        line=dict(color=CHART["p50"], width=3.2),
        showlegend=False,
    ))

    if goal_amount > 0:
        fig.add_hline(
            y=goal_amount,
            line_width=1.5,
            line_dash="dash",
            line_color=COLORS["goal"],
            annotation_text=f"Streef {format_euro(goal_amount)}",
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color=COLORS["goal"],
        )

    for x0, x1, _ in phase_ranges[:-1]:
        fig.add_vline(x=x1, line_width=1, line_dash="dot", line_color="#cbd5e1")

    yaxis: dict = dict(
        title="Vermogen (€)",
        gridcolor="#f1f5f9",
        fixedrange=True,
        zeroline=False,
    )
    if use_log:
        yaxis["type"] = "log"
        yaxis["tickformat"] = ","
    else:
        yaxis["tickformat"] = ","
        yaxis["range"] = [y_min, y_max]

    fig.update_layout(
        template="plotly_white",
        height=460,
        margin=dict(l=52, r=16, t=36, b=44),
        showlegend=False,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title=x_title, gridcolor="#f1f5f9"),
        yaxis=yaxis,
    )
    return fig, footnote
