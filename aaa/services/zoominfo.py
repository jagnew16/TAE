"""ZoomInfo contact lookup (mock). A real integration would call ZoomInfo's search API."""

from difflib import get_close_matches

from .. import store
from .crm import normalize, similarity


def _companies():
    return store.load("zoominfo")["companies"]


def find_company(company: str) -> dict | None:
    companies = _companies()
    best = max(companies, key=lambda c: similarity(company, c["company"]))
    return best if similarity(company, best["company"]) >= 0.9 else None


def find_contacts(company: str, title_keywords: list[str] | None = None) -> dict:
    match = find_company(company)
    if match is None:
        names = {normalize(c["company"]): c["company"] for c in _companies()}
        close = get_close_matches(normalize(company), list(names), n=3, cutoff=0.6)
        return {"found": False, "company": company, "did_you_mean": [names[c] for c in close]}
    contacts = match["contacts"]
    if title_keywords:
        keys = [k.lower() for k in title_keywords]
        contacts = [c for c in contacts if any(k in c["title"].lower() for k in keys)] or contacts
    return {
        "found": True, "source": "ZoomInfo (mock)", "company": match["company"],
        "website": match["domain"], "instagram": match["instagram"], "hq_state": match["hq_state"],
        "employees": match["employees"], "contacts": contacts,
    }
