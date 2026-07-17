"""Input data model for a miner and its assets, loaded from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Asset:
    """A single mining project / deposit.

    Recoverable ounces can be given directly (``recoverable_koz``) or derived
    from a resource statement (``resource_mt`` * ``grade_gpt`` * ``recovery``).
    All monetary values are USD; ounces are troy ounces.
    """

    name: str
    # Resource / production
    recoverable_koz: float | None = None  # thousand recoverable oz over life
    resource_mt: float | None = None  # million tonnes of ore
    grade_gpt: float | None = None  # grams gold per tonne
    recovery: float = 0.90  # metallurgical recovery fraction
    resource_koz_insitu: float | None = None  # in-situ M&I oz for EV/oz screen
    annual_koz: float = 100.0  # steady-state annual production (koz)
    ramp_years: int = 1  # years to ramp to steady state
    # Economics
    aisc: float = 1300.0  # all-in sustaining cost, USD/oz
    initial_capex_musd: float = 0.0  # pre-production build capex (USD millions)
    start_year: int = 1  # years from valuation date to first production
    payability: float = 1.0  # fraction of gold price realized (refining/stream)
    # Risk
    discount_rate: float | None = None  # overrides company discount rate
    risk_factor: float = 1.0  # 0-1 multiplier for probability of success

    def recovered_ounces(self) -> float:
        """Total recoverable ounces over life of mine (troy oz)."""
        if self.recoverable_koz is not None:
            return self.recoverable_koz * 1_000.0
        if self.resource_mt is not None and self.grade_gpt is not None:
            tonnes = self.resource_mt * 1_000_000.0
            grams = tonnes * self.grade_gpt
            oz = grams / 31.1035  # grams per troy ounce
            return oz * self.recovery
        raise ValueError(
            f"Asset '{self.name}': provide recoverable_koz or resource_mt+grade_gpt"
        )

    def insitu_resource_oz(self) -> float:
        """In-situ ounces used for the EV/oz screen."""
        if self.resource_koz_insitu is not None:
            return self.resource_koz_insitu * 1_000.0
        if self.resource_mt is not None and self.grade_gpt is not None:
            return (self.resource_mt * 1_000_000.0 * self.grade_gpt) / 31.1035
        # Fall back to recoverable (gross-up by recovery).
        return self.recovered_ounces() / max(self.recovery, 1e-6)


@dataclass
class CompanyInputs:
    name: str
    ticker: str | None = None
    assets: list[Asset] = field(default_factory=list)
    # Corporate adjustments (USD millions)
    net_debt_musd: float = 0.0  # debt minus cash (positive = net debt)
    other_obligations_musd: float = 0.0  # streams / gold prepay / deferred
    reclamation_musd: float = 0.0
    annual_ga_musd: float = 0.0  # corporate G&A per year
    ga_years: int = 10  # years of G&A to capitalize in NAV
    # Assumptions
    discount_rate: float = 0.08
    tax_rate: float = 0.25
    life_cap_years: int = 25
    shares_outstanding: float | None = None  # fully diluted; else use live
    notes: str = ""

    @staticmethod
    def from_dict(d: dict) -> "CompanyInputs":
        assets = [Asset(**a) for a in d.get("assets", [])]
        top = {k: v for k, v in d.items() if k != "assets"}
        return CompanyInputs(assets=assets, **top)


def load_company(path: str | Path) -> CompanyInputs:
    data = json.loads(Path(path).read_text())
    return CompanyInputs.from_dict(data)
