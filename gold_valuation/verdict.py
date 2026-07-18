"""Turn valuation metrics into an under/over-valued verdict."""

from __future__ import annotations

from dataclasses import dataclass

# Rough peer benchmarks for single-asset-to-multi-asset North American gold
# developers/producers. Used only as directional context, not precise cutoffs.
DEVELOPER_PNAV_FAIR = 0.6  # developers commonly trade ~0.3-0.7x NAV
PRODUCER_PNAV_FAIR = 1.0
DEVELOPER_EV_PER_OZ = (50.0, 150.0)  # USD/oz M&I typical band for developers


@dataclass
class Verdict:
    price: float | None
    navps: float | None
    p_nav: float | None
    ev_per_oz: float | None
    upside_pct: float | None  # (navps/price - 1)
    label: str
    rationale: list[str]


def _classify(p_nav: float | None) -> str:
    if p_nav is None:
        return "Indeterminate"
    if p_nav < 0.5:
        return "Undervalued (deep discount)"
    if p_nav < 0.85:
        return "Undervalued"
    if p_nav <= 1.15:
        return "Fairly valued"
    if p_nav <= 1.5:
        return "Overvalued"
    return "Overvalued (rich)"


def assess(
    price: float | None,
    navps: float | None,
    p_nav: float | None,
    ev_per_oz: float | None,
    fair_pnav: float = DEVELOPER_PNAV_FAIR,
) -> Verdict:
    upside = None
    if price and navps is not None and price > 0:
        upside = navps / price - 1.0

    label = _classify(p_nav)
    rationale: list[str] = []

    if p_nav is not None:
        rationale.append(
            f"Trades at {p_nav:.2f}x NAV vs a ~{fair_pnav:.2f}x fair multiple for "
            f"this stage; {'below' if p_nav < fair_pnav else 'above'} peers."
        )
    if upside is not None:
        direction = "upside" if upside >= 0 else "downside"
        rationale.append(
            f"NAV/share ${navps:,.2f} vs price ${price:,.2f} => {upside*100:+.0f}% {direction}."
        )
    if ev_per_oz is not None:
        lo, hi = DEVELOPER_EV_PER_OZ
        if ev_per_oz < lo:
            rationale.append(f"EV/oz ${ev_per_oz:,.0f} is below the ${lo:,.0f}-${hi:,.0f} developer band (cheap on resources).")
        elif ev_per_oz > hi:
            rationale.append(f"EV/oz ${ev_per_oz:,.0f} is above the ${lo:,.0f}-${hi:,.0f} developer band (rich on resources).")
        else:
            rationale.append(f"EV/oz ${ev_per_oz:,.0f} sits within the ${lo:,.0f}-${hi:,.0f} developer band.")

    return Verdict(
        price=price, navps=navps, p_nav=p_nav, ev_per_oz=ev_per_oz,
        upside_pct=upside, label=label, rationale=rationale,
    )


def implied_price_at_fair(navps: float | None, fair_pnav: float) -> float | None:
    if navps is None:
        return None
    return navps * fair_pnav
