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

## Two valuation paths

1. **Published-NPV (PEA) mode** — `--pea` (recommended for i-80). Uses the
   company's own after-tax NPVs per project from its filed PEAs/feasibility
   studies, interpolated vs gold price, then bridged to an equity NAV via net
   debt, royalty/stream obligations, corporate G&A and reclamation. This is the
   most authoritative sum-of-the-parts. i-80's PEAs are all at a 5% discount
   rate, so the sensitivity here is on gold price.
2. **Bottom-up DCF mode** — `--company`. An independent, simplified life-of-mine
   DCF from resource/production/AISC/capex inputs. Useful as a conservative
   cross-check; it values gold only and is generally lower than the PEA NPVs
   because of simplified timing/tax and per-asset risk haircuts.

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
# Published-NPV (PEA) valuation of i-80 — live gold + IAUX price
python valuate.py --pea data/i80gold_pea.json

# Same, pinned to the PEA base gold price
python valuate.py --pea data/i80gold_pea.json --gold 2175 --no-live

# Bottom-up DCF cross-check
python valuate.py --company data/i80gold.json

# Derive an implied price at 0.5x P/NAV (either mode)
python valuate.py --pea data/i80gold_pea.json --p-nav 0.5
```

Key flags: `--gold`, `--discount` (DCF only), `--share-price`, `--shares`,
`--ticker`, `--no-live`, `--p-nav`.

**Extrapolation caveat:** in PEA mode, NPVs are linearly extrapolated above each
project's highest published gold-price point (i-80's is $3,000/oz). At today's
much higher spot gold this materially raises NAV, especially for the
long-life, high-leverage Mineral Point pit — treat prices far above $3,000/oz
as indicative only.

## Data provenance (i-80)

- **Per-project after-tax NPVs, IRR, AISC, capex, production, mine life:** i-80
  PEAs filed 2025-03-31, as summarized in the July 2026 corporate presentation.
- **Resource tonnes/grades:** Mineral Resource Estimate as at 2024-12-31.
- **Cash, debt, NSR royalty, silver-purchase derivative, reclamation, shares:**
  2026 Q1 10-Q (balance sheet 2026-03-31; shares outstanding as at 2026-05-12).

## Input format

See `data/i80gold.json`. Each asset accepts either recoverable ounces directly
(`recoverable_koz`) or a resource statement (`resource_mt` + `grade_gpt` +
`recovery`), plus `annual_koz`, `aisc`, `initial_capex_musd`, `start_year`, an
optional per-asset `discount_rate`, and a `risk_factor` (0–1) to probability-
weight earlier-stage assets. Corporate lines: `net_debt_musd`,
`other_obligations_musd` (streams / prepay), `reclamation_musd`,
`annual_ga_musd`, `tax_rate`, `discount_rate`, `shares_outstanding`.

## ⚠️ Data caveat

The i-80 datasets are populated from public filings (see **Data provenance**
above) and are current as of the July 2026 presentation / Q1 2026 10-Q. They
are still a simplification of the underlying technical reports (e.g. the
bottom-up mode values gold only; corporate G&A and obligation treatment are
approximations). Refresh them from i-80's latest **S-K 1300 / NI 43-101**
reports and financial statements before relying on the output for decisions,
and this is not investment advice.

## Tests

```bash
pytest -q
```
