from aaa import store
from aaa.services import bdsa, crm


def unclaimed_brand(state):
    """A brand tracked by BDSA in `state` that has no CRM record."""
    for row in bdsa.top_brands(state, 50, "quarter")["brands"]:
        if crm.find_matches(row["brand"]) == []:
            return row["brand"]
    raise AssertionError("seed data has no unclaimed brand")


def test_matching_ignores_legal_suffixes_but_not_real_differences():
    assert crm.similarity("Ember Labs LLC", "Ember Labs") == 1.0
    assert crm.similarity("Sierra Pine Supply, Inc.", "sierra pine supply") == 1.0
    assert crm.similarity("North Fork Farms", "North Fork Provisions") < crm.MATCH_THRESHOLD
    assert crm.similarity("Marigold Botanicals", "Marigold Harvest") < crm.MATCH_THRESHOLD


def test_existing_customer_is_flagged_and_excluded(alice):
    check = crm.check_prospect(alice, "Sierra Pine Supply")
    assert check["verdict"] == "existing_customer"
    assert "exclude" in check["guidance"].lower()
    # Alice owns it, so she gets full detail including contacts.
    assert check["matches"][0]["contacts"]


def test_another_reps_record_shows_only_status_and_owner(alice):
    check = crm.check_prospect(alice, "Ember Labs")
    assert check["verdict"] == "existing_record"
    match = check["matches"][0]
    assert match["owner"] == "Ben Okafor"
    assert match["status"] == "Contacted"
    for private in ("contact_email", "contact_name", "recent_activities", "notes"):
        assert private not in match


def test_manager_sees_full_detail(dana):
    match = crm.check_prospect(dana, "Ember Labs")["matches"][0]
    assert match["contact_email"]
    assert "recent_activities" in match


def test_match_by_website_domain(alice):
    check = crm.check_prospect(alice, "Totally Different Name", website="https://www.emberlabs.example/shop")
    assert check["verdict"] == "existing_record"


def test_create_lead_refuses_duplicates(alice):
    before = len(store.load("crm")["leads"])
    result = crm.create_lead(alice, "Ember Labs", "CA")
    assert result["created"] is False
    assert len(store.load("crm")["leads"]) == before


def test_create_lead_in_own_territory(alice):
    brand = unclaimed_brand("CA")
    result = crm.create_lead(alice, brand, "CA", contact_name="Pat Doe")
    assert result["created"] and result["owner"] == "Alice Moreno"
    assert crm.check_prospect(alice, brand)["verdict"] == "existing_record"


def test_create_lead_outside_territory_goes_to_territory_owner(alice):
    brand = unclaimed_brand("MI")
    result = crm.create_lead(alice, brand, "MI")
    assert result["created"] and result["owner"] == "Ben Okafor"
    assert "territory" in result["note"]


def test_insights_restricted_to_owner(alice, ben):
    assert "error" in crm.account_insights(alice, "ACC-1005")
    assert "categories" in crm.account_insights(ben, "ACC-1005")


def test_insights_show_decline_and_lapsed_category(alice):
    declining = crm.account_insights(alice, "ACC-1002")
    assert declining["total_change_pct"] < 0
    lapsed = crm.account_insights(alice, "ACC-1003")
    assert any(c["lapsed"] for c in lapsed["categories"])


def test_insights_find_whitespace(alice):
    """Copper Gardens sells a category at retail that it buys no packaging for from us."""
    insights = crm.account_insights(alice, "ACC-1002")
    gap = insights["whitespace"][0]
    assert gap["last_quarter_revenue"] > 0
    assert gap["we_could_supply"] not in {c["category"] for c in insights["categories"]}


def test_pipeline_only_lists_own_records(alice, dana):
    mine = crm.my_pipeline(alice)
    assert {r["owner_id"] for r in mine["accounts"] + mine["leads"]} == {"alice"}
    everyone = crm.my_pipeline(dana)
    assert {r["owner_id"] for r in everyone["accounts"]} == {"alice", "ben", "carla"}
