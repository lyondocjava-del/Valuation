"""Live market data: equity price / shares (yfinance) and gold spot price."""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass
class MarketData:
    """Live (or overridden) market inputs used for market-based multiples."""

    gold_price: float  # USD per troy ounce
    share_price: float | None  # in the ticker's native currency
    shares_outstanding: float | None
    ticker: str | None
    currency: str | None
    gold_source: str
    share_source: str

    @property
    def market_cap(self) -> float | None:
        if self.share_price is None or self.shares_outstanding is None:
            return None
        return self.share_price * self.shares_outstanding


def _last_close(ticker: str) -> float | None:
    """Most recent close via yfinance history (more robust than fast_info)."""
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if len(hist):
            return float(hist["Close"].iloc[-1])
    except Exception:
        return None
    return None


def _fast_info(ticker: str) -> tuple[float | None, float | None, str | None]:
    price = shares = None
    currency = None
    try:
        fi = yf.Ticker(ticker).fast_info
        price = fi.get("last_price")
        shares = fi.get("shares")
        currency = fi.get("currency")
    except Exception:
        pass
    if price is None:
        price = _last_close(ticker)
    return (
        float(price) if price is not None else None,
        float(shares) if shares is not None else None,
        currency,
    )


def fetch_market_data(
    ticker: str | None = "IAUX",
    gold_ticker: str = "GC=F",
    gold_price_override: float | None = None,
    share_price_override: float | None = None,
    shares_override: float | None = None,
) -> MarketData:
    """Fetch live market data, honoring any provided overrides.

    Falls back gracefully: if a live fetch fails and no override is given,
    the corresponding field is left as ``None`` (market multiples that need
    it are then reported as unavailable rather than crashing).
    """
    # Gold price.
    if gold_price_override is not None:
        gold_price = float(gold_price_override)
        gold_source = "override"
    else:
        gp = _last_close(gold_ticker)
        gold_price = gp if gp is not None else 0.0
        gold_source = f"live:{gold_ticker}" if gp is not None else "unavailable"

    # Equity.
    share_price = share_price_override
    shares = shares_override
    currency = None
    share_source = "override"
    if ticker and (share_price is None or shares is None):
        live_price, live_shares, currency = _fast_info(ticker)
        if share_price is None:
            share_price = live_price
        if shares is None:
            shares = live_shares
        share_source = f"live:{ticker}"

    return MarketData(
        gold_price=gold_price,
        share_price=share_price,
        shares_outstanding=shares,
        ticker=ticker,
        currency=currency,
        gold_source=gold_source,
        share_source=share_source,
    )
