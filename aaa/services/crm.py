"""CRM rules: duplicate checks, visibility, lead creation, ownership, sales insights.

These rules are enforced here in code, not left to the model. The model can't
create a duplicate lead or see another rep's account details even if it tries.

Company rules this prototype assumes (confirm with the business):
- You see full detail on records you own; managers see all records.
- Anyone can see that a record exists, with its status and owner, so reps
  don't collide on outreach.
- A new lead belongs to the rep whose territory covers the prospect's state.
  If no rep covers that state, the rep who created it owns it.
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher

from .. import store
from ..context import RepContext, rep_names
from . import bdsa

LEGAL_SUFFIXES = {"inc", "llc", "co", "corp", "corporation", "company", "ltd", "the"}
MATCH_THRESHOLD = 0.9


def normalize(name: str) -> str:
    words = re.sub(r"[^a-z0-9& ]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in LEGAL_SUFFIXES)


def similarity(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _domain(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"^https?://", "", value.strip().lower())
    return value.split("/")[0].removeprefix("www.")


def _crm():
    return store.load("crm")


def _summary(kind: str, rec: dict, names: dict) -> dict:
    """What anyone may see: enough to avoid conflicting outreach, nothing more."""
    return {
        "record_type": kind,
        "id": rec["id"],
        "name": rec.get("name") or rec.get("company"),
        "state": rec["state"],
        "status": rec["status"],
        "is_customer": rec.get("type") == "customer",
        "owner": names.get(rec["owner"], rec["owner"]),
        "owner_id": rec["owner"],
    }


def _full(kind: str, rec: dict, crm: dict, names: dict) -> dict:
    out = _summary(kind, rec, names) | {k: v for k, v in rec.items() if k not in ("owner",)}
    if kind == "account":
        out["contacts"] = [c for c in crm["contacts"] if c["account_id"] == rec["id"]]
    out["recent_activities"] = sorted(
        (a for a in crm["activities"] if a["record_id"] == rec["id"]),
        key=lambda a: a["date"], reverse=True)[:5]
    return out


def find_matches(company: str, website: str | None = None, crm: dict | None = None) -> list[tuple[str, dict, float]]:
    """Every account, lead, or contact's account that looks like `company`."""
    crm = crm or _crm()
    domain = _domain(website)
    hits = []
    for kind, rec in [("account", a) for a in crm["accounts"]] + [("lead", l) for l in crm["leads"]]:
        name = rec.get("name") or rec.get("company")
        score = similarity(company, name)
        if domain and domain == _domain(rec.get("website")):
            score = 1.0
        if score >= MATCH_THRESHOLD:
            hits.append((kind, rec, score))
    # A matching contact email domain also ties the prospect to an existing account.
    if domain:
        account_ids = {c["account_id"] for c in crm["contacts"] if c["email"].endswith("@" + domain)}
        for acc in crm["accounts"]:
            if acc["id"] in account_ids and not any(h[1]["id"] == acc["id"] for h in hits):
                hits.append(("account", acc, 1.0))
    return sorted(hits, key=lambda h: h[2], reverse=True)


def check_prospect(ctx: RepContext, company: str, website: str | None = None) -> dict:
    """Requirement 4, steps 1-3: is this prospect already a customer, account, contact, or lead?"""
    crm = _crm()
    names = rep_names()
    hits = find_matches(company, website, crm)
    matches = []
    for kind, rec, score in hits:
        view = _full(kind, rec, crm, names) if ctx.can_see(rec["owner"]) else _summary(kind, rec, names)
        view["match_confidence"] = round(score, 2)
        matches.append(view)

    if any(m["is_customer"] for m in matches):
        verdict = "existing_customer"
        guidance = ("Existing customer: exclude from new-prospect outreach. "
                    "Coordinate with the account owner instead.")
    elif matches:
        verdict = "existing_record"
        mine = all(m["owner_id"] == ctx.rep_id for m in matches)
        guidance = ("You already own this record; continue working it rather than creating a new lead."
                    if mine else
                    "Another rep owns this record. Don't create a lead or reach out without talking to the owner.")
    else:
        verdict = "no_match"
        guidance = "No existing record. Safe to create a new lead."
    return {"company": company, "verdict": verdict, "guidance": guidance, "matches": matches}


def owner_for_state(state: str, creating_rep: RepContext) -> str:
    if state in creating_rep.territory:
        return creating_rep.rep_id
    for rep in store.load("reps"):
        if state in rep["territory"]:
            return rep["rep_id"]
    return creating_rep.rep_id


def create_lead(ctx: RepContext, company: str, state: str, website: str | None = None,
                contact_name: str | None = None, contact_title: str | None = None,
                contact_email: str | None = None, contact_phone: str | None = None,
                source: str = "AAA") -> dict:
    """Requirement 4, step 4. Re-runs the duplicate check itself, so it can't be skipped."""
    check = check_prospect(ctx, company, website)
    if check["verdict"] != "no_match":
        return {"created": False, "reason": "Duplicate check found an existing record.", **check}

    crm = _crm()
    owner = owner_for_state(state.upper(), ctx)
    lead = {
        "id": store.next_id("LEAD", crm["leads"]), "company": company, "state": state.upper(),
        "owner": owner, "status": "New", "source": source, "created": ctx.today.isoformat(),
        "website": _domain(website), "contact_name": contact_name, "contact_title": contact_title,
        "contact_email": contact_email, "contact_phone": contact_phone,
    }
    crm["leads"].append(lead)
    crm["activities"].append({"id": store.next_id("ACT", crm["activities"]), "record_id": lead["id"],
                              "rep": ctx.rep_id, "type": "Lead created",
                              "summary": f"Created by {ctx.name} via AAA", "date": ctx.today.isoformat()})
    store.save("crm", crm)

    names = rep_names()
    result = {"created": True, "lead_id": lead["id"], "owner": names.get(owner, owner)}
    if owner != ctx.rep_id:
        result["note"] = (f"{state.upper()} is {names.get(owner, owner)}'s territory, so the lead "
                          f"was assigned to them per the ownership rules.")
    return result


def get_record(ctx: RepContext, record_id: str) -> dict | None:
    crm = _crm()
    for kind, coll in (("account", "accounts"), ("lead", "leads")):
        for rec in crm[coll]:
            if rec["id"] == record_id:
                names = rep_names()
                return _full(kind, rec, crm, names) if ctx.can_see(rec["owner"]) else _summary(kind, rec, names)
    return None


def owner_of(record_id: str) -> str | None:
    crm = _crm()
    for rec in crm["accounts"] + crm["leads"]:
        if rec["id"] == record_id:
            return rec["owner"]
    return None


def log_activity(ctx: RepContext, record_id: str, activity_type: str, summary: str) -> dict:
    owner = owner_of(record_id)
    if owner is None:
        return {"logged": False, "reason": f"No CRM record {record_id}."}
    if not ctx.can_see(owner):
        return {"logged": False, "reason": f"{record_id} is owned by {rep_names().get(owner, owner)}."}
    crm = _crm()
    act = {"id": store.next_id("ACT", crm["activities"]), "record_id": record_id, "rep": ctx.rep_id,
           "type": activity_type, "summary": summary, "date": ctx.today.isoformat()}
    crm["activities"].append(act)
    store.save("crm", crm)
    return {"logged": True, "activity_id": act["id"]}


def my_pipeline(ctx: RepContext) -> dict:
    crm = _crm()
    names = rep_names()
    accounts = [_summary("account", a, names) for a in crm["accounts"] if ctx.can_see(a["owner"])]
    leads = [_summary("lead", l, names) for l in crm["leads"] if ctx.can_see(l["owner"])]
    return {"accounts": accounts, "leads": leads}


def account_insights(ctx: RepContext, account_id: str) -> dict:
    """Purchasing patterns from our order history for one customer the rep can see."""
    crm = _crm()
    acc = next((a for a in crm["accounts"] if a["id"] == account_id), None)
    if acc is None:
        return {"error": f"No account {account_id}."}
    if not ctx.can_see(acc["owner"]):
        return {"error": f"{account_id} is owned by {rep_names().get(acc['owner'], acc['owner'])}; "
                         "order history is restricted to the owner."}
    orders = [o for o in crm["orders"] if o["account_id"] == account_id]
    if not orders:
        return {"account": acc["name"], "note": "No order history (not a customer yet)."}

    months = sorted({o["month"] for o in orders})
    by_cat = defaultdict(lambda: defaultdict(float))
    for o in orders:
        by_cat[o["category"]][o["month"]] += o["amount"]

    def window(series, ms):
        return sum(series.get(m, 0) for m in ms)

    recent, prior = months[-3:], months[-6:-3]
    categories = []
    for cat, series in by_cat.items():
        r, p = window(series, recent), window(series, prior)
        categories.append({
            "category": cat,
            "last_3_months": round(r),
            "prior_3_months": round(p),
            "change_pct": round((r - p) / p * 100, 1) if p else None,
            "last_order_month": max(series),
            "lapsed": max(series) < months[-1],
        })
    total_r = sum(c["last_3_months"] for c in categories)
    total_p = sum(c["prior_3_months"] for c in categories)
    return {
        "account": acc["name"],
        "through_month": months[-1],
        "total_last_3_months": total_r,
        "total_change_pct": round((total_r - total_p) / total_p * 100, 1) if total_p else None,
        "categories": sorted(categories, key=lambda c: c["last_3_months"], reverse=True),
        "whitespace": whitespace(acc["name"], set(by_cat)),
    }


def whitespace(account_name: str, categories_bought: set[str]) -> list[dict]:
    """Product categories the brand sells at retail (BDSA) but buys no packaging for from us."""
    packaging_for = store.load("catalog")["packaging_for_category"]
    retail = bdsa.brand_categories(lambda name: similarity(name, account_name) >= MATCH_THRESHOLD)
    gaps = [{"brand_sells": cat, "we_could_supply": packaging_for[cat], **numbers}
            for cat, numbers in retail.items() if packaging_for.get(cat) not in categories_bought]
    return sorted(gaps, key=lambda g: g["last_quarter_revenue"], reverse=True)
