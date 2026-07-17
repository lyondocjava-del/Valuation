"""Valuation from a company's *published* per-asset after-tax NPVs.

For companies that have filed PEAs / feasibility studies (like i-80 Gold), the
most authoritative sum-of-the-parts is management's own after-tax NPV for each
project. Each asset carries NPV data points at several gold prices; this module
interpolates / extrapolates NPV vs gold price, sums to a gross project NAV,
bridges to an equity NAV via corporate adjustments, and derives NAVPS and P/NAV.

The PEA discount rate is fixed by the studies (i-80's are at 5%), so the
sensitivity here is on gold price, not discount rate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .market import MarketData


@dataclass
class PublishedAsset:
    name: str
    # Sorted-by-gold-price NPV curve: list of [gold_price_usd_per_oz, npv_musd].
    npv_points: list[list[float]]
    annual_koz: float | None = None
    mine_life_years: float | None = None
    aisc: float | None = None
    start_year: str | None = None
    status: str | None = None

    def npv_at(self, gold_price: float) -> float:
        pts = sorted(self.npv_points, key=lambda p: p[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if gold_price <= xs[0]:
            # Linear extrapolation off the low end (clamped at >= 0).
            slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
            return max(0.0, ys[0] + slope * (gold_price - xs[0]))
        if gold_price >= xs[-1]:
            slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
            return ys[-1] + slope * (gold_price - xs[-1])
        for i in range(len(xs) - 1):
            if xs[i] <= gold_price <= xs[i + 1]:
                frac = (gold_price - xs[i]) / (xs[i + 1] - xs[i])
                return ys[i] + frac * (ys[i + 1] - ys[i])
        return ys[-1]


@dataclass
class PublishedCompany:
    name: str
    ticker: str | None = None
    pea_discount_rate: float = 0.05
    assets: list[PublishedAsset] = field(default_factory=list)
    # Corporate bridge (USD millions). Positive numbers reduce equity NAV
    # unless noted; cash is netted inside ``net_debt_musd``.
    net_debt_musd: float = 0.0  # total debt - cash (negative = net cash)
    nsr_royalty_musd: float = 0.0  # value ceded via NSR royalty financing
    stream_musd: float = 0.0  # silver/gold stream obligation
    other_obligations_musd: float = 0.0
    corporate_ga_annual_musd: float = 0.0
    corporate_ga_years: int = 10
    reclamation_musd: float = 0.0  # only if NOT already in project NPVs
    shares_outstanding: float | None = None
    notes: str = ""
    sources: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "PublishedCompany":
        assets = [PublishedAsset(**a) for a in d.get("assets", [])]
        top = {k: v for k, v in d.items() if k != "assets"}
        return PublishedCompany(assets=assets, **top)


@dataclass
class PublishedResult:
    company: str
    gold_price: float
    discount_rate: float
    per_asset: list[tuple[str, float]]  # (name, npv_musd)
    gross_nav_musd: float
    bridge: list[tuple[str, float]]  # (label, +/- musd)
    equity_nav_musd: float
    shares: float | None
    navps: float | None
    market_cap_musd: float | None
    p_nav: float | None


def load_published(path: str | Path) -> PublishedCompany:
    return PublishedCompany.from_dict(json.loads(Path(path).read_text()))


def value_published(
    company: PublishedCompany,
    market: MarketData,
    gold_price: float | None = None,
) -> PublishedResult:
    gp = gold_price if gold_price is not None else market.gold_price

    per_asset = [(a.name, a.npv_at(gp)) for a in company.assets]
    gross = sum(v for _, v in per_asset)

    ga_pv = 0.0
    for y in range(1, company.corporate_ga_years + 1):
        ga_pv += company.corporate_ga_annual_musd / (1 + company.pea_discount_rate) ** y

    bridge = [
        ("Gross project NAV (Σ PEA NPVs)", gross),
        ("Less: net debt (– = net cash)", -company.net_debt_musd),
        ("Less: NSR royalty ceded", -company.nsr_royalty_musd),
        ("Less: stream obligation", -company.stream_musd),
        ("Less: other obligations", -company.other_obligations_musd),
        ("Less: corporate G&A (PV)", -ga_pv),
        ("Less: reclamation (if not in NPVs)", -company.reclamation_musd),
    ]
    equity = gross - (
        company.net_debt_musd
        + company.nsr_royalty_musd
        + company.stream_musd
        + company.other_obligations_musd
        + ga_pv
        + company.reclamation_musd
    )

    shares = company.shares_outstanding or market.shares_outstanding
    navps = equity * 1e6 / shares if shares else None

    market_cap_musd = market.market_cap / 1e6 if market.market_cap is not None else None
    p_nav = (market_cap_musd / equity) if (market_cap_musd and equity) else None

    return PublishedResult(
        company=company.name,
        gold_price=gp,
        discount_rate=company.pea_discount_rate,
        per_asset=per_asset,
        gross_nav_musd=gross,
        bridge=bridge,
        equity_nav_musd=equity,
        shares=shares,
        navps=navps,
        market_cap_musd=market_cap_musd,
        p_nav=p_nav,
    )


def published_gold_sensitivity(
    company: PublishedCompany,
    market: MarketData,
    gold_prices: list[float],
) -> list[tuple[float, float | None, float | None]]:
    """Return [(gold_price, navps, p_nav), ...] over a gold-price sweep."""
    out = []
    for gp in gold_prices:
        r = value_published(company, market, gold_price=gp)
        out.append((gp, r.navps, r.p_nav))
    return out
