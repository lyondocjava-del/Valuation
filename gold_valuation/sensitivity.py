"""Gold-price x discount-rate sensitivity grid for NAV per share."""

from __future__ import annotations

import pandas as pd

from .market import MarketData
from .model import CompanyInputs
from .valuation import value_company


def navps_sensitivity(
    company: CompanyInputs,
    market: MarketData,
    gold_prices: list[float],
    discount_rates: list[float],
) -> pd.DataFrame:
    """Return a DataFrame of NAV/share: rows=gold price, cols=discount rate."""
    data: dict[str, list[float | None]] = {}
    for dr in discount_rates:
        col = f"{dr*100:.0f}%"
        data[col] = []
        for gp in gold_prices:
            res = value_company(company, market, gold_price=gp, discount_rate=dr,
                                force_asset_discount=True)
            data[col].append(round(res.navps, 2) if res.navps is not None else None)
    idx = [f"${gp:,.0f}" for gp in gold_prices]
    return pd.DataFrame(data, index=idx)
