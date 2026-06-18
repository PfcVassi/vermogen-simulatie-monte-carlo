"""
Kernlogica voor Monte Carlo vermogenssimulatie (huidig + nieuw belastingstelsel).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np

CONTRIBUTION_FREQUENCIES = ("maandelijks", "kwartaal", "jaarlijks")
CASH_BUFFER_MONTHS = 24
DEFAULT_BORROW_RATE_ANNUAL = 0.05
BOX3_EXEMPTION_PARTNER = 115_368.0
BOX3_EXEMPTION_SINGLE = 57_684.0
BOX3_RETURN_EXEMPTION_PARTNER = 2_000.0
BOX3_RETURN_EXEMPTION_SINGLE = 1_000.0


@dataclass(frozen=True)
class PhaseConfig:
    name: str = "fase 1"
    years: int = 10
    mu: float = 0.08
    sigma: float = 0.15
    contribution_amount: int = 0
    contribution_frequency: str = "maandelijks"
    contribution_increase: float = 0.0
    extra_contribution_yearly: int = 0
    withdrawal: int = 0
    withdrawal_monthly: bool = True
    index_withdrawal: bool = True


DEFAULT_PHASES: tuple[PhaseConfig, ...] = (
    PhaseConfig(),
)


@dataclass(frozen=True)
class SimulationConfig:
    n_runs: int = 10_000
    random_seed: int | None = 42
    start_capital: float = 100_000.0
    inflation_rate: float = 0.02
    phases: tuple[PhaseConfig, ...] = DEFAULT_PHASES
    fiscaal_partner: bool = True
    box3_tax_rate: float = 0.36
    box3_forfait_rate: float = 0.0604
    borrow_rate_annual: float = DEFAULT_BORROW_RATE_ANNUAL
    cash_buffer_months: int = CASH_BUFFER_MONTHS

    @property
    def box3_wealth_exemption(self) -> float:
        return BOX3_EXEMPTION_PARTNER if self.fiscaal_partner else BOX3_EXEMPTION_SINGLE

    @property
    def box3_return_exemption(self) -> float:
        return BOX3_RETURN_EXEMPTION_PARTNER if self.fiscaal_partner else BOX3_RETURN_EXEMPTION_SINGLE

    @property
    def simulation_start_year(self) -> int:
        return date.today().year

    @property
    def horizon_years(self) -> int:
        return sum(p.years for p in self.phases)

    @property
    def simulation_end_year(self) -> int:
        return max(0, self.horizon_years - 1)

    @property
    def phase_boundaries(self) -> list[tuple[int, str]]:
        boundaries: list[tuple[int, str]] = []
        cumulative = 0
        for phase in self.phases[:-1]:
            cumulative += phase.years
            boundaries.append((cumulative, phase.name))
        return boundaries


@dataclass
class SimulationResult:
    paths_huidig: np.ndarray
    paths_nieuw: np.ndarray
    paths_zonder_belasting: np.ndarray
    cumulative_tax_huidig: np.ndarray
    cumulative_tax_nieuw: np.ndarray
    cumulative_contributions: np.ndarray
    cumulative_withdrawals: np.ndarray
    timestamps: list[datetime]


def _phase_at_year(config: SimulationConfig, year: int) -> tuple[PhaseConfig, int]:
    elapsed = 0
    for phase in config.phases:
        if year < elapsed + phase.years:
            return phase, year - elapsed
        elapsed += phase.years
    last = config.phases[-1]
    return last, max(0, last.years - 1)


def _monthly_log_returns(
    mu: float, sigma: float, n_runs: int, rng: np.random.Generator,
) -> np.ndarray:
    dt = 1.0 / 12.0
    z = rng.standard_normal(n_runs)
    log_return = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    return np.exp(log_return) - 1.0


def _inflation_factor(config: SimulationConfig, year: int, month_in_year: int) -> float:
    years_elapsed = year + month_in_year / 12.0
    return (1.0 + config.inflation_rate) ** years_elapsed


def _indexed_exemption(config: SimulationConfig, year: int) -> float:
    return config.box3_wealth_exemption * _inflation_factor(config, year, 11)


def _indexed_return_exemption(config: SimulationConfig, year: int) -> float:
    return config.box3_return_exemption * _inflation_factor(config, year, 11)


def _calendar_timestamp(config: SimulationConfig, year: int, month_in_year: int) -> datetime:
    calendar_year = config.simulation_start_year + year
    last_day = calendar.monthrange(calendar_year, month_in_year + 1)[1]
    return datetime(calendar_year, month_in_year + 1, last_day, 12, 0, 0, tzinfo=timezone.utc)


def _contribution_this_month(
    phase: PhaseConfig,
    month_in_year: int,
    growth: float,
    inflation: float,
) -> float:
    amount = phase.contribution_amount * growth * inflation
    freq = phase.contribution_frequency
    if freq == "maandelijks":
        return amount
    if freq == "kwartaal":
        return amount if month_in_year % 3 == 0 else 0.0
    return amount if month_in_year == 0 else 0.0


def _monthly_cash_flows(
    config: SimulationConfig,
    phase: PhaseConfig,
    year: int,
    year_in_phase: int,
    month_in_year: int,
) -> tuple[float, float]:
    inflation = _inflation_factor(config, year, month_in_year)
    growth = (1.0 + phase.contribution_increase) ** year_in_phase

    contribution = _contribution_this_month(phase, month_in_year, growth, inflation)
    if month_in_year == 0 and phase.extra_contribution_yearly > 0:
        contribution += phase.extra_contribution_yearly * inflation

    withdrawal_infl = inflation if phase.index_withdrawal else 1.0
    withdrawal_nominal = phase.withdrawal * withdrawal_infl

    if phase.withdrawal <= 0:
        withdrawal = 0.0
    elif phase.withdrawal_monthly:
        withdrawal = withdrawal_nominal
    elif month_in_year == 11:
        withdrawal = withdrawal_nominal
    else:
        withdrawal = 0.0

    return contribution, withdrawal


def _monthly_borrow_rate(annual_rate: float) -> float:
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0


def _indexed_monthly_withdrawal(
    config: SimulationConfig,
    phase: PhaseConfig,
    year: int,
    month_in_year: int,
) -> float:
    """Maandelijks equivalent van de onttrekking (voor cash-buffer berekening)."""
    if phase.withdrawal <= 0:
        return 0.0
    inflation = _inflation_factor(config, year, month_in_year)
    nominal = phase.withdrawal * (inflation if phase.index_withdrawal else 1.0)
    if phase.withdrawal_monthly:
        return nominal
    return nominal / 12.0


def _target_cash_buffer(
    config: SimulationConfig,
    phase: PhaseConfig,
    year: int,
    month_in_year: int,
) -> float:
    monthly_wd = _indexed_monthly_withdrawal(config, phase, year, month_in_year)
    if monthly_wd <= 0:
        return 0.0
    return config.cash_buffer_months * monthly_wd


def _pay_tax_from_pots(
    invested: np.ndarray,
    cash: np.ndarray,
    tax: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Box 3-belasting: eerst uit beleggingen, daarna uit cash."""
    pay = np.maximum(tax, 0.0)
    from_invested = np.minimum(pay, np.maximum(invested, 0.0))
    invested = invested - from_invested
    pay = pay - from_invested
    cash = cash - pay
    return invested, cash


def _process_month_pots(
    invested: np.ndarray,
    cash: np.ndarray,
    monthly_return: np.ndarray,
    contribution: float,
    withdrawal: float,
    target_buffer: float,
    borrow_monthly: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Twee-potten maandcyclus (vectorized over alle runs):
    A. Buffer aanvullen bij positief rendement
    B. Rendement op invested (leenrente bij schuld)
    C. Inleg naar invested, onttrekking eerst uit cash
    """
    # A — buffer aanvullen in winstmaanden
    gap = np.maximum(target_buffer - cash, 0.0)
    replenish = (monthly_return > 0) & (gap > 0) & (invested > 0)
    transfer = np.where(replenish, np.minimum(gap, invested), 0.0)
    invested = invested - transfer
    cash = cash + transfer

    # B — rendement alleen op invested; schuld groeit met leenrente
    in_debt = invested < 0
    invested = np.where(
        in_debt,
        invested * (1.0 + borrow_monthly),
        invested * (1.0 + monthly_return),
    )

    # C — cashflows
    invested = invested + contribution
    from_cash = np.minimum(withdrawal, cash)
    cash = cash - from_cash
    invested = invested - (withdrawal - from_cash)

    return invested, cash


def _apply_box3_huidig(config: SimulationConfig, wealth: np.ndarray, year: int) -> np.ndarray:
    exemption = _indexed_exemption(config, year)
    taxable_base = np.maximum(wealth - exemption, 0.0)
    return taxable_base * config.box3_forfait_rate * config.box3_tax_rate


def _apply_box3_nieuw(
    config: SimulationConfig,
    wealth: np.ndarray,
    year_start_wealth: np.ndarray,
    year_contributions: float,
    year_withdrawals: float,
    loss_carryforward: np.ndarray,
    year: int,
) -> tuple[np.ndarray, np.ndarray]:
    year_return = wealth - year_start_wealth - year_contributions + year_withdrawals
    tax = np.zeros_like(wealth)
    return_exemption = _indexed_return_exemption(config, year)

    gains = year_return > 0.0
    losses = year_return <= 0.0

    loss_carryforward[losses] += -year_return[losses]

    if np.any(gains):
        gain = year_return[gains]
        carry = loss_carryforward[gains]
        net = gain - carry
        used_carry = np.minimum(carry, gain)
        loss_carryforward[gains] -= used_carry

        taxable = np.maximum(net - return_exemption, 0.0)
        tax[gains] = taxable * config.box3_tax_rate

    return tax, loss_carryforward


def run_simulation(config: SimulationConfig) -> SimulationResult:
    n_months = config.horizon_years * 12
    n_runs = config.n_runs
    rng = np.random.default_rng(config.random_seed)
    borrow_monthly = _monthly_borrow_rate(config.borrow_rate_annual)

    start = config.start_capital
    invested_h = np.full(n_runs, start, dtype=np.float64)
    invested_n = np.full(n_runs, start, dtype=np.float64)
    invested_z = np.full(n_runs, start, dtype=np.float64)
    cash_h = np.zeros(n_runs, dtype=np.float64)
    cash_n = np.zeros(n_runs, dtype=np.float64)
    cash_z = np.zeros(n_runs, dtype=np.float64)
    loss_carryforward = np.zeros(n_runs, dtype=np.float64)

    paths_huidig = np.empty((n_runs, n_months), dtype=np.float64)
    paths_nieuw = np.empty((n_runs, n_months), dtype=np.float64)
    paths_zonder = np.empty((n_runs, n_months), dtype=np.float64)
    cumulative_tax_huidig = np.zeros((n_runs, n_months), dtype=np.float64)
    cumulative_tax_nieuw = np.zeros((n_runs, n_months), dtype=np.float64)
    cumulative_contributions = np.zeros(n_months, dtype=np.float64)
    cumulative_withdrawals = np.zeros(n_months, dtype=np.float64)
    timestamps: list[datetime] = []

    year_start_nieuw = np.full(n_runs, start, dtype=np.float64)
    year_contributions = 0.0
    year_withdrawals = 0.0
    running_contrib = 0.0
    running_withdraw = 0.0

    for month_idx in range(n_months):
        year = month_idx // 12
        month_in_year = month_idx % 12

        if month_in_year == 0 and month_idx > 0:
            year_start_nieuw = invested_n + cash_n
            year_contributions = 0.0
            year_withdrawals = 0.0

        phase, year_in_phase = _phase_at_year(config, year)
        monthly_return = _monthly_log_returns(phase.mu, phase.sigma, n_runs, rng)
        monthly_contribution, monthly_withdrawal = _monthly_cash_flows(
            config, phase, year, year_in_phase, month_in_year,
        )
        target_buffer = _target_cash_buffer(config, phase, year, month_in_year)

        year_contributions += monthly_contribution
        year_withdrawals += monthly_withdrawal
        running_contrib += monthly_contribution
        running_withdraw += monthly_withdrawal

        invested_h, cash_h = _process_month_pots(
            invested_h, cash_h, monthly_return,
            monthly_contribution, monthly_withdrawal, target_buffer, borrow_monthly,
        )
        invested_n, cash_n = _process_month_pots(
            invested_n, cash_n, monthly_return,
            monthly_contribution, monthly_withdrawal, target_buffer, borrow_monthly,
        )
        invested_z, cash_z = _process_month_pots(
            invested_z, cash_z, monthly_return,
            monthly_contribution, monthly_withdrawal, target_buffer, borrow_monthly,
        )

        wealth_huidig = invested_h + cash_h
        wealth_nieuw = invested_n + cash_n
        wealth_zonder = invested_z + cash_z

        if month_in_year == 11:
            tax_h = _apply_box3_huidig(config, wealth_huidig, year)
            invested_h, cash_h = _pay_tax_from_pots(invested_h, cash_h, tax_h)
            wealth_huidig = invested_h + cash_h
            cumulative_tax_huidig[:, month_idx] = (
                cumulative_tax_huidig[:, month_idx - 1] if month_idx else 0.0
            ) + tax_h

            tax_n, loss_carryforward = _apply_box3_nieuw(
                config,
                wealth_nieuw,
                year_start_nieuw,
                year_contributions,
                year_withdrawals,
                loss_carryforward,
                year,
            )
            invested_n, cash_n = _pay_tax_from_pots(invested_n, cash_n, tax_n)
            wealth_nieuw = invested_n + cash_n
            cumulative_tax_nieuw[:, month_idx] = (
                cumulative_tax_nieuw[:, month_idx - 1] if month_idx else 0.0
            ) + tax_n
        elif month_idx > 0:
            cumulative_tax_huidig[:, month_idx] = cumulative_tax_huidig[:, month_idx - 1]
            cumulative_tax_nieuw[:, month_idx] = cumulative_tax_nieuw[:, month_idx - 1]

        paths_huidig[:, month_idx] = wealth_huidig
        paths_nieuw[:, month_idx] = wealth_nieuw
        paths_zonder[:, month_idx] = wealth_zonder
        cumulative_contributions[month_idx] = running_contrib
        cumulative_withdrawals[month_idx] = running_withdraw
        timestamps.append(_calendar_timestamp(config, year, month_in_year))

    return SimulationResult(
        paths_huidig=paths_huidig,
        paths_nieuw=paths_nieuw,
        paths_zonder_belasting=paths_zonder,
        cumulative_tax_huidig=cumulative_tax_huidig,
        cumulative_tax_nieuw=cumulative_tax_nieuw,
        cumulative_contributions=cumulative_contributions,
        cumulative_withdrawals=cumulative_withdrawals,
        timestamps=timestamps,
    )


def compute_percentiles(wealth_paths: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.percentile(wealth_paths, 10, axis=0),
        np.percentile(wealth_paths, 50, axis=0),
        np.percentile(wealth_paths, 90, axis=0),
    )


def median_run_index(paths: np.ndarray) -> int:
    end_p50 = np.percentile(paths[:, -1], 50)
    return int(np.argmin(np.abs(paths[:, -1] - end_p50)))


def describe_tax_logic(config: SimulationConfig, tax_mode: str) -> str:
    """Tekstuele uitleg van de toegepaste Box 3-logica voor de UI."""
    infl_pct = config.inflation_rate * 100
    partner_lbl = "met fiscaal partner" if config.fiscaal_partner else "zonder fiscaal partner (alleenstaand)"
    voet = config.box3_wealth_exemption
    rend_vrij = config.box3_return_exemption
    tarief = int(round(config.box3_tax_rate * 100))
    forfait = config.box3_forfait_rate * 100

    if tax_mode == "Uit":
        return (
            "Box 3-belasting is **uitgeschakeld**. Het vermogen in de grafiek volgt alleen "
            "marktrendement, inleg, onttrekkingen en de cash-buffer — zonder jaarlijkse "
            "belastingaftrek."
        )
    if tax_mode.startswith("Huidig"):
        return (
            f"**Huidig stelsel ({partner_lbl}):** er wordt jaarlijks **{tarief}%** belasting "
            f"berekend over een fictief rendement van **{forfait:.2f}%** op al het vermogen "
            f"boven de heffingsvrije voet van **€{voet:,.0f}** (punt als decimaalteken), "
            f"welke jaarlijks meestijgt met de ingevoerde inflatie (**{infl_pct:.1f}%**)."
        ).replace(",", ".")
    return (
        f"**Nieuw stelsel ({partner_lbl}, onder voorbehoud wetgeving):** er wordt jaarlijks "
        f"**{tarief}%** belasting berekend over het **werkelijk behaalde positieve rendement**, "
        f"met verrekening van verliezen uit eerdere jaren. De eerste **€{rend_vrij:,.0f}** "
        f"(geïndexeerd met inflatie **{infl_pct:.1f}%**) aan werkelijk rendement is heffingsvrij. "
        f"Er is geen heffingsvrije vermogensvoet meer."
    ).replace(",", ".")
