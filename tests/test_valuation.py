"""Sanity tests for the valuation engine."""

from __future__ import annotations

from gold_valuation.market import MarketData
from gold_valuation.model import Asset, CompanyInputs
from gold_valuation.valuation import value_company


def _market(gold=2400.0, price=2.0, shares=1_000_000_000):
    return MarketData(
        gold_price=gold, share_price=price, shares_outstanding=shares,
        ticker="TEST", currency="USD", gold_source="test", share_source="test",
    )


def _company(**kw):
    base = dict(
        name="TestCo", ticker="TEST", discount_rate=0.08, tax_rate=0.25,
        assets=[Asset(name="A", recoverable_koz=1000, resource_koz_insitu=1500,
                      annual_koz=100, aisc=1200, initial_capex_musd=100,
                      start_year=1)],
    )
    base.update(kw)
    return CompanyInputs(**base)


def test_higher_gold_price_increases_nav():
    c, m = _company(), _market()
    low = value_company(c, m, gold_price=2000.0)
    high = value_company(c, m, gold_price=3000.0)
    assert high.corporate_nav_musd > low.corporate_nav_musd


def test_higher_discount_lowers_nav():
    c, m = _company(), _market()
    lo = value_company(c, m, discount_rate=0.05, force_asset_discount=True)
    hi = value_company(c, m, discount_rate=0.12, force_asset_discount=True)
    assert lo.corporate_nav_musd > hi.corporate_nav_musd


def test_ev_per_oz_and_pnav_computed():
    res = value_company(_company(), _market())
    assert res.ev_per_oz is not None and res.ev_per_oz > 0
    assert res.p_nav is not None


def test_resource_from_grade_and_tonnage():
    a = Asset(name="G", resource_mt=10.0, grade_gpt=3.1103, recovery=0.9)
    # 10Mt * 3.1103 g/t / 31.1035 g/oz = ~1.0 Moz in-situ
    assert abs(a.insitu_resource_oz() - 1_000_000) < 5_000
    assert abs(a.recovered_ounces() - 900_000) < 5_000


def test_missing_shares_gives_no_navps():
    c = _company()
    m = _market(shares=None)
    m.shares_outstanding = None
    res = value_company(c, m)
    assert res.navps is None
