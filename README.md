# Gold Miner Valuation Toolkit

A small, general-purpose engine for valuing development / production-stage gold
miners. Ships with an **i-80 Gold (IAUX)** input set, but works for any miner
through a JSON input file.

It produces the metrics you actually use to value a gold miner:

- **Sum-of-the-parts NAV / DCF** — a life-of-mine, after-tax discounted cash
  flow for each asset, netted for corporate G&A, net debt, stream / gold-prepay
  obligations and reclamation → **NAV** and **NAV per share (NAVPS)**.
- **EV per ounce** — enterprise value / total in-situ resource ounces.
- **P/NAV** — market cap / NAV, plus an implied share price at a target P/NAV.
- **Gold-price × discount-rate sensitivity grid** for NAVPS.

Live share price / shares (via `yfinance`) and the gold spot price (`GC=F`) are
pulled automatically, with overrides for everything.

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
# Live gold price + live IAUX equity data
python valuate.py --company data/i80gold.json

# Fixed gold price, no network
python valuate.py --company data/i80gold.json --gold 2400 --no-live

# Derive an implied price at 0.5x P/NAV
python valuate.py --company data/i80gold.json --p-nav 0.5
```

Key flags: `--gold`, `--discount`, `--share-price`, `--shares`, `--ticker`,
`--no-live`, `--p-nav`.

## Input format

See `data/i80gold.json`. Each asset accepts either recoverable ounces directly
(`recoverable_koz`) or a resource statement (`resource_mt` + `grade_gpt` +
`recovery`), plus `annual_koz`, `aisc`, `initial_capex_musd`, `start_year`, an
optional per-asset `discount_rate`, and a `risk_factor` (0–1) to probability-
weight earlier-stage assets. Corporate lines: `net_debt_musd`,
`other_obligations_musd` (streams / prepay), `reclamation_musd`,
`annual_ga_musd`, `tax_rate`, `discount_rate`, `shares_outstanding`.

## ⚠️ Data caveat

The i-80 dataset shipped here contains **placeholder estimates for
demonstration only**. Before relying on any output, replace every asset figure
and corporate line with numbers from i-80's latest **S-K 1300 / NI 43-101
technical reports** and most recent financial statements. The engine is the
deliverable; the numbers are yours to supply.

## Tests

```bash
pytest -q
```
