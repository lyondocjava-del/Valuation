"""Sum-of-the-parts NAV / DCF engine plus market-based multiples."""

from __future__ import annotations

from dataclasses import dataclass, field

from .market import MarketData
from .model import Asset, CompanyInputs


def irr(cashflows: list[float], lo: float = -0.9999, hi: float = 100.0) -> float | None:
    """After-tax IRR of a cash-flow stream (index = period, cashflows[0] = t0).

    Returns the rate where NPV = 0 via bisection, or ``None`` when there is no
    sign change (e.g. all-positive or all-negative flows) so IRR is undefined.
    """
    if not any(cf < 0 for cf in cashflows) or not any(cf > 0 for cf in cashflows):
        return None

    def npv(r: float) -> float:
        return sum(cf / (1.0 + r) ** t for t, cf in enumerate(cashflows))

    flo, fhi = npv(lo), npv(hi)
    if flo == 0:
        return lo
    if flo * fhi > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2.0
        fm = npv(mid)
        if abs(fm) < 1e-7:
            return mid
        if flo * fm < 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2.0


@dataclass
class AssetValuation:
    name: str
    recovered_oz: float
    life_years: float
    npv_musd: float  # after-tax NPV of the asset (USD millions)
    undiscounted_fcf_musd: float
    yearly_cf_musd: list[float] = field(default_factory=list)  # unrisked, t0..N
    irr: float | None = None  # unrisked after-tax IRR


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
    portfolio_irr: float | None = None  # firm-level after-tax IRR (unrisked)

    def summary_rows(self) -> list[tuple[str, str]]:
        def money(x):
            return f"${x:,.0f}M" if x is not None else "n/a"

        rows = [
            ("Company", self.company),
            ("Gold price (USD/oz)", f"${self.gold_price:,.0f}"),
            ("Discount rate", f"{self.discount_rate*100:.1f}%"),
            ("Gross asset NAV", money(self.gross_asset_nav_musd)),
            ("Corporate NAV", money(self.corporate_nav_musd)),
            (
                "Portfolio IRR (after-tax)",
                f"{self.portfolio_irr*100:.1f}%" if self.portfolio_irr is not None else "n/a",
            ),
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

    # Build an unrisked yearly cash-flow vector (index = year, 0 = valuation date).
    max_year = asset.start_year + life_cap + 1
    cf = [0.0] * (max_year + 1)

    # Pre-production capex spread over the build period (years 1..start_year).
    for by in range(1, asset.start_year + 1):
        cf[by] -= asset.initial_capex_musd / asset.start_year

    remaining = recovered
    year = asset.start_year
    produced_years = 0
    while remaining > 1e-6 and produced_years < life_cap:
        # Ramp: fraction of steady-state in the first ``ramp_years``.
        ramp = min(1.0, (produced_years + 1) / max(asset.ramp_years, 1))
        oz = min(annual_oz * ramp, remaining)
        remaining -= oz
        pretax = oz * margin_per_oz / 1e6  # USD millions
        after_tax = pretax * (1 - tax) if pretax > 0 else pretax
        cf[year] += after_tax
        year += 1
        produced_years += 1

    # Discounted NPV from the same stream, then probability-weight.
    npv = sum(c / (1 + rate) ** t for t, c in enumerate(cf)) * asset.risk_factor
    undiscounted = sum(cf) * asset.risk_factor

    return AssetValuation(
        name=asset.name,
        recovered_oz=recovered,
        life_years=round(life, 1),
        npv_musd=npv,
        undiscounted_fcf_musd=undiscounted,
        yearly_cf_musd=cf,
        irr=irr(cf),
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

    # Firm-level (portfolio) IRR from the aggregated unrisked project cash flows,
    # net of corporate G&A. Independent of the discount rate.
    horizon = max((len(av.yearly_cf_musd) for av in asset_vals), default=0)
    portfolio_cf = [0.0] * horizon
    for av in asset_vals:
        for t, c in enumerate(av.yearly_cf_musd):
            portfolio_cf[t] += c
    for y in range(1, min(company.ga_years, horizon - 1) + 1):
        portfolio_cf[y] -= company.annual_ga_musd
    portfolio_irr = irr(portfolio_cf)

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
        portfolio_irr=portfolio_irr,
    )
    return result
