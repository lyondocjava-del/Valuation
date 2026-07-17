"""Gold miner valuation toolkit.

A small, general-purpose engine for valuing development / production stage
gold miners via sum-of-the-parts NAV (DCF), EV per ounce, and P/NAV, with a
gold-price x discount-rate sensitivity grid. Ships with an i-80 Gold (IAUX)
input dataset, but works for any miner via a JSON input file.
"""

from .market import MarketData, fetch_market_data
from .model import Asset, CompanyInputs, load_company
from .valuation import ValuationResult, value_company
from .sensitivity import navps_sensitivity
from .published import (
    PublishedAsset,
    PublishedCompany,
    PublishedResult,
    load_published,
    published_gold_sensitivity,
    value_published,
)

__all__ = [
    "MarketData",
    "fetch_market_data",
    "Asset",
    "CompanyInputs",
    "load_company",
    "ValuationResult",
    "value_company",
    "navps_sensitivity",
    "PublishedAsset",
    "PublishedCompany",
    "PublishedResult",
    "load_published",
    "value_published",
    "published_gold_sensitivity",
]
