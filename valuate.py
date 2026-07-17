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
    load_published,
    navps_sensitivity,
    published_gold_sensitivity,
    value_company,
    value_published,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--company", help="Path to bottom-up DCF company JSON inputs")
    src.add_argument("--pea", help="Path to published-NPV (PEA) company JSON inputs")
    p.add_argument("--ticker", default=None, help="Override equity ticker (default: from JSON)")
    p.add_argument("--gold", type=float, default=None, help="Override gold price USD/oz")
    p.add_argument("--share-price", type=float, default=None, help="Override share price")
    p.add_argument("--shares", type=float, default=None, help="Override shares outstanding")
    p.add_argument("--discount", type=float, default=None, help="Override discount rate (e.g. 0.08)")
    p.add_argument("--p-nav", type=float, default=None,
                   help="Target P/NAV multiple to derive an implied share price")
    p.add_argument("--no-live", action="store_true", help="Skip live data fetch")
    return p.parse_args()


def _market_for(args, ticker, fallback_shares):
    if args.no_live:
        return fetch_market_data(
            ticker=None,
            gold_price_override=args.gold if args.gold is not None else 2400.0,
            share_price_override=args.share_price,
            shares_override=args.shares or fallback_shares,
        )
    return fetch_market_data(
        ticker=ticker,
        gold_price_override=args.gold,
        share_price_override=args.share_price,
        shares_override=args.shares,
    )


def _print_header(name, market):
    print("\n" + "=" * 68)
    print(f" VALUATION — {name}")
    print("=" * 68)
    print(f" Gold price source : {market.gold_source}  (${market.gold_price:,.0f}/oz)")
    print(f" Equity source     : {market.share_source}"
          + (f"  (price={market.share_price}, ccy={market.currency})"
             if market.share_price is not None else ""))


def run_published(args) -> None:
    company = load_published(args.pea)
    ticker = args.ticker or company.ticker
    market = _market_for(args, ticker, company.shares_outstanding)
    result = value_published(company, market)

    _print_header(company.name, market)
    print(f" PEA discount rate : {company.pea_discount_rate*100:.0f}% (fixed by studies)")
    if company.notes:
        print("\n [i] " + company.notes)

    print("\n-- Per-asset after-tax NPV (interpolated to current gold price) --")
    arows = []
    for a, (name, npv) in zip(company.assets, result.per_asset):
        airr = a.irr_at(result.gold_price)
        arows.append([name, a.status or "", a.start_year or "",
                      f"{a.annual_koz:,.0f} koz" if a.annual_koz else "",
                      f"${a.aisc:,.0f}" if a.aisc else "", f"${npv:,.0f}M",
                      f"{airr*100:.0f}%" if airr is not None else "n/a"])
    print(tabulate(arows, headers=["Asset", "Status", "Start", "Annual",
                                    "AISC/oz", f"NPV @ ${result.gold_price:,.0f}", "IRR"],
                   tablefmt="github"))

    print("\n-- NAV bridge (gross project NAV → equity) --")
    print(tabulate([[lbl, f"${v:,.0f}M"] for lbl, v in result.bridge],
                   headers=["Item", "USD"], tablefmt="github"))

    def fmt(x, s=""):
        return f"{s}{x:,.2f}" if x is not None else "n/a"

    summ = [
        ("Equity NAV", f"${result.equity_nav_musd:,.0f}M"),
        ("Fully diluted shares", f"{result.shares:,.0f}" if result.shares else "n/a"),
        ("NAV per share", fmt(result.navps, "$")),
        ("Market cap", f"${result.market_cap_musd:,.0f}M"
                       if result.market_cap_musd is not None else "n/a"),
        ("P/NAV", f"{result.p_nav:.2f}x" if result.p_nav is not None else "n/a"),
    ]
    print("\n-- Company summary --")
    print(tabulate(summ, headers=["Metric", "Value"], tablefmt="github"))

    if args.p_nav is not None and result.navps is not None:
        print(f"\n Implied price @ {args.p_nav:.2f}x P/NAV: ${result.navps*args.p_nav:,.2f}")

    base = market.gold_price or 2400.0
    golds = sorted({round(base * f, -1) for f in (0.7, 0.85, 1.0, 1.15, 1.3)}
                   | {2175.0, 3000.0})
    print("\n-- NAV/share & P/NAV vs gold price (PEA discount rate fixed) --")
    srows = [[f"${gp:,.0f}", fmt(navps, "$"), f"{pnav:.2f}x" if pnav else "n/a"]
             for gp, navps, pnav in published_gold_sensitivity(company, market, golds)]
    print(tabulate(srows, headers=["Gold $/oz", "NAV/share", "P/NAV"],
                   tablefmt="github"))
    print()


def main() -> None:
    args = parse_args()
    if args.pea:
        run_published(args)
        return

    company = load_company(args.company)
    ticker = args.ticker or company.ticker
    market = _market_for(args, ticker, company.shares_outstanding)

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
         f"${av.npv_musd:,.0f}M",
         f"{av.irr*100:.0f}%" if av.irr is not None else "n/a"]
        for av in result.asset_values
    ]
    print(tabulate(rows, headers=["Asset", "Recoverable", "Life", "NPV", "IRR"],
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
