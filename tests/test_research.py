import pytest

from aaa.services import bdsa
from aaa.specialists.contacts import lookup_contacts
from aaa.specialists.market_intel import _crm_flag


@pytest.mark.parametrize("n", [10, 20, 30, 50])
def test_top_n_brands(n):
    result = bdsa.top_brands("CA", n, "quarter")
    assert len(result["brands"]) == n
    revenues = [b["revenue"] for b in result["brands"]]
    assert revenues == sorted(revenues, reverse=True)


def test_periods_cover_the_right_months():
    assert bdsa.top_brands("MI", 5, "month")["covering"] == "2026-09"
    assert bdsa.top_brands("MI", 5, "year")["covering"] == "2025-10 to 2026-09"


def test_unknown_state_is_an_error():
    with pytest.raises(ValueError):
        bdsa.top_brands("TX")


def test_brand_detail_and_trends():
    top = bdsa.top_brands("CA", 1, "quarter")["brands"][0]["brand"]
    detail = bdsa.brand_detail(top, "CA")
    assert detail["rank"]["quarter"] == 1
    assert len(detail["monthly_revenue"]) == 12
    trends = bdsa.category_trends("CA")["categories"]
    beverages = next(c for c in trends if c["category"] == "Beverages")
    flower = next(c for c in trends if c["category"] == "Flower")
    assert beverages["qoq_growth_pct"] > flower["qoq_growth_pct"]


def test_top_brands_flag_customers_and_other_reps_records(alice):
    assert _crm_flag(alice, "Sierra Pine Supply")["ok_to_prospect"] is False
    flag = _crm_flag(alice, "Ember Labs")
    assert flag["ok_to_prospect"] is False and "Ben Okafor" in flag["crm"]


def test_contacts_withheld_for_another_reps_account(alice, ben):
    withheld = lookup_contacts(alice, "Ember Labs")
    assert withheld["withheld"] is True and "Ben Okafor" in withheld["reason"]
    assert "contacts" not in withheld
    assert lookup_contacts(ben, "Ember Labs")["contacts"]


def test_contacts_for_unclaimed_company(alice):
    from tests.test_crm import unclaimed_brand
    result = lookup_contacts(alice, unclaimed_brand("CA"), ["procurement", "purchasing", "operations"])
    assert result["found"] and result["contacts"]
    assert result["crm_check"]["verdict"] == "no_match"
    assert all("555-01" in c["phone"] for c in result["contacts"])
