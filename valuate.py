#!/usr/bin/env python3
"""CLI: value a gold miner via sum-of-the-parts NAV, EV/oz, P/NAV + sensitivity.

Examples:
    python valuate.py --company data/i80gold.json
    python valuate.py --company data/i80gold.json --gold 2400 --no-live
    python valuate.py --company data/i80gold.json --p-nav 0.5
"""

from __future__ import annotations

import argparse

from tabulate import tabulate

from gold_valuation import (
    fetch_market_data,
    load_company,
    navps_sensitivity,
    value_company,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--company", required=True, help="Path to company JSON inputs")
    p.add_argument("--ticker", default=None, help="Override equity ticker (default: from JSON)")
    p.add_argument("--gold", type=float, default=None, help="Override gold price USD/oz")
    p.add_argument("--share-price", type=float, default=None, help="Override share price")
    p.add_argument("--shares", type=float, default=None, help="Override shares outstanding")
    p.add_argument("--discount", type=float, default=None, help="Override discount rate (e.g. 0.08)")
    p.add_argument("--p-nav", type=float, default=None,
                   help="Target P/NAV multiple to derive an implied share price")
    p.add_argument("--no-live", action="store_true", help="Skip live data fetch")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    company = load_company(args.company)
    ticker = args.ticker or company.ticker

    if args.no_live:
        market = fetch_market_data(
            ticker=None,
            gold_price_override=args.gold if args.gold is not None else 2400.0,
            share_price_override=args.share_price,
            shares_override=args.shares or company.shares_outstanding,
        )
    else:
        market = fetch_market_data(
            ticker=ticker,
            gold_price_override=args.gold,
            share_price_override=args.share_price,
            shares_override=args.shares,
        )

    result = value_company(company, market, discount_rate=args.discount)

    print("\n" + "=" * 68)
    print(f" VALUATION — {company.name}")
    print("=" * 68)
    print(f" Gold price source : {market.gold_source}")
    print(f" Equity source     : {market.share_source}"
          + (f"  (price={market.share_price}, ccy={market.currency})"
             if market.share_price is not None else ""))
    if company.notes:
        print("\n [!] " + company.notes)

    print("\n-- Per-asset NAV (after-tax NPV) --")
    rows = [
        [av.name, f"{av.recovered_oz/1e3:,.0f} koz", f"{av.life_years} yr",
         f"${av.npv_musd:,.0f}M"]
        for av in result.asset_values
    ]
    print(tabulate(rows, headers=["Asset", "Recoverable", "Life", "NPV"],
                   tablefmt="github"))

    print("\n-- Company summary --")
    print(tabulate(result.summary_rows(), headers=["Metric", "Value"],
                   tablefmt="github"))

    if args.p_nav is not None and result.navps is not None:
        implied = result.navps * args.p_nav
        print(f"\n Implied price @ {args.p_nav:.2f}x P/NAV: ${implied:,.2f}")

    # Sensitivity grid.
    base_gold = market.gold_price or 2400.0
    golds = [round(base_gold * f, -1) for f in (0.8, 0.9, 1.0, 1.1, 1.2, 1.3)]
    discs = [0.05, 0.07, 0.08, 0.10, 0.12]
    print("\n-- NAV/share sensitivity (rows = gold USD/oz, cols = discount rate) --")
    grid = navps_sensitivity(company, market, golds, discs)
    print(tabulate(grid, headers=grid.columns, tablefmt="github", floatfmt=",.2f"))
    print()


if __name__ == "__main__":
    main()
