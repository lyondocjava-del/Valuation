"""Sum-of-the-parts NAV / DCF engine plus market-based multiples."""

from __future__ import annotations

from dataclasses import dataclass, field

from .market import MarketData
from .model import Asset, CompanyInputs


@dataclass
class AssetValuation:
    name: str
    recovered_oz: float
    life_years: float
    npv_musd: float  # after-tax NPV of the asset (USD millions)
    undiscounted_fcf_musd: float


@dataclass
class ValuationResult:
    company: str
    gold_price: float
    discount_rate: float
    asset_values: list[AssetValuation] = field(default_factory=list)
    gross_asset_nav_musd: float = 0.0
    corporate_nav_musd: float = 0.0
    shares: float | None = None
    navps: float | None = None
    # Market-based
    market_cap_musd: float | None = None
    ev_musd: float | None = None
    ev_per_oz: float | None = None
    p_nav: float | None = None
    total_resource_oz: float = 0.0

    def summary_rows(self) -> list[tuple[str, str]]:
        def money(x):
            return f"${x:,.0f}M" if x is not None else "n/a"

        rows = [
            ("Company", self.company),
            ("Gold price (USD/oz)", f"${self.gold_price:,.0f}"),
            ("Discount rate", f"{self.discount_rate*100:.1f}%"),
            ("Gross asset NAV", money(self.gross_asset_nav_musd)),
            ("Corporate NAV", money(self.corporate_nav_musd)),
            ("Fully diluted shares", f"{self.shares:,.0f}" if self.shares else "n/a"),
            ("NAV per share", f"${self.navps:,.2f}" if self.navps is not None else "n/a"),
            ("Market cap", money(self.market_cap_musd)),
            ("Enterprise value (EV)", money(self.ev_musd)),
            (
                "EV / in-situ oz",
                f"${self.ev_per_oz:,.0f}/oz" if self.ev_per_oz is not None else "n/a",
            ),
            ("P/NAV", f"{self.p_nav:.2f}x" if self.p_nav is not None else "n/a"),
            ("Total in-situ resource", f"{self.total_resource_oz/1e6:,.2f} Moz"),
        ]
        return rows


def _value_asset(asset: Asset, gold_price: float, disc: float, tax: float,
                 life_cap: int, force_disc: bool = False) -> AssetValuation:
    if force_disc or asset.discount_rate is None:
        rate = disc
    else:
        rate = asset.discount_rate
    recovered = asset.recovered_ounces()
    annual_oz = asset.annual_koz * 1_000.0

    life = recovered / annual_oz if annual_oz > 0 else 0.0
    life = min(life, life_cap)

    margin_per_oz = gold_price * asset.payability - asset.aisc  # USD/oz

    npv = 0.0
    undiscounted = 0.0
    remaining = recovered
    year = asset.start_year

    # Pre-production capex, discounted over the build period (years 1..start_year).
    for by in range(1, asset.start_year + 1):
        npv -= (asset.initial_capex_musd / asset.start_year) / (1 + rate) ** by
    undiscounted -= asset.initial_capex_musd

    produced_years = 0
    while remaining > 1e-6 and produced_years < life_cap:
        # Ramp: fraction of steady-state in the first ``ramp_years``.
        ramp = min(1.0, (produced_years + 1) / max(asset.ramp_years, 1))
        oz = min(annual_oz * ramp, remaining)
        remaining -= oz
        pretax = oz * margin_per_oz / 1e6  # USD millions
        after_tax = pretax * (1 - tax) if pretax > 0 else pretax
        npv += after_tax / (1 + rate) ** year
        undiscounted += after_tax
        year += 1
        produced_years += 1

    npv *= asset.risk_factor
    undiscounted *= asset.risk_factor
    return AssetValuation(
        name=asset.name,
        recovered_oz=recovered,
        life_years=round(life, 1),
        npv_musd=npv,
        undiscounted_fcf_musd=undiscounted,
    )


def value_company(
    company: CompanyInputs,
    market: MarketData,
    gold_price: float | None = None,
    discount_rate: float | None = None,
    force_asset_discount: bool = False,
) -> ValuationResult:
    """Run the full sum-of-the-parts valuation.

    ``gold_price`` / ``discount_rate`` override the company/market defaults
    (used by the sensitivity grid). When ``force_asset_discount`` is True the
    supplied discount rate is applied to every asset, ignoring per-asset
    ``discount_rate`` overrides (so a sensitivity sweep actually moves NAV).
    """
    gp = gold_price if gold_price is not None else market.gold_price
    disc = discount_rate if discount_rate is not None else company.discount_rate

    asset_vals = [
        _value_asset(a, gp, disc, company.tax_rate, company.life_cap_years,
                     force_disc=force_asset_discount)
        for a in company.assets
    ]
    gross = sum(av.npv_musd for av in asset_vals)

    # Corporate deductions.
    ga_pv = 0.0
    for y in range(1, company.ga_years + 1):
        ga_pv += company.annual_ga_musd / (1 + disc) ** y

    corporate = (
        gross
        - ga_pv
        - company.net_debt_musd
        - company.other_obligations_musd
        - company.reclamation_musd
    )

    shares = company.shares_outstanding or market.shares_outstanding
    navps = None
    if shares:
        navps = corporate * 1e6 / shares  # per share, USD

    total_resource_oz = sum(a.insitu_resource_oz() for a in company.assets)

    # Market-based multiples.
    market_cap_musd = ev_musd = ev_per_oz = p_nav = None
    if market.market_cap is not None:
        market_cap_musd = market.market_cap / 1e6
        ev_musd = (
            market_cap_musd
            + company.net_debt_musd
            + company.other_obligations_musd
        )
        if total_resource_oz > 0:
            ev_per_oz = ev_musd * 1e6 / total_resource_oz
        if corporate not in (0, None):
            p_nav = market_cap_musd / corporate

    result = ValuationResult(
        company=company.name,
        gold_price=gp,
        discount_rate=disc,
        asset_values=asset_vals,
        gross_asset_nav_musd=gross,
        corporate_nav_musd=corporate,
        shares=shares,
        navps=navps,
        market_cap_musd=market_cap_musd,
        ev_musd=ev_musd,
        ev_per_oz=ev_per_oz,
        p_nav=p_nav,
        total_resource_oz=total_resource_oz,
    )
    return result
