"""Website and Instagram launch monitoring (requirement 6).

The real version would poll each watched site (RSS, sitemap, or page diff) and
each Instagram business account (Instagram Graph API) on a schedule. Here, new
posts come from aaa/seed/launch_feed.json. The job:
  1. collects posts from watched accounts that it hasn't processed yet,
  2. keeps the ones that look like product launches (cheap keyword filter first),
  3. has the launch classifier agent confirm and summarize them (optional),
  4. notifies whoever owns the CRM record at that moment.
"""

import re

from .. import store
from ..context import RepContext, rep_names
from . import crm

LAUNCH_WORDS = re.compile(
    r"\b(introduc\w*|launch\w*|new (product|line|drop|flavor)|newest|now available|"
    r"just dropped|available now|hits shelves|coming soon)\b", re.I)


def _norm_account(value: str) -> str:
    return value.lower().lstrip("@").removeprefix("www.")


def watchlist() -> list[dict]:
    return store.load("watchlist")


def my_watchlist(ctx: RepContext) -> list[dict]:
    return [w for w in watchlist() if ctx.can_see(crm.owner_of(w["record_id"]) or "")]


def add(ctx: RepContext, record_id: str, website: str | None = None, instagram: str | None = None) -> dict:
    owner = crm.owner_of(record_id)
    if owner is None:
        return {"added": False, "reason": f"No CRM record {record_id}."}
    if not ctx.can_see(owner):
        return {"added": False, "reason": f"{record_id} is owned by {rep_names().get(owner, owner)}."}
    if not website and not instagram:
        return {"added": False, "reason": "Give a website, an Instagram handle, or both."}
    record = crm.get_record(ctx, record_id)
    items = watchlist()
    entry = {"id": store.next_id("WATCH", items), "record_id": record_id, "company": record["name"],
             "website": _norm_account(website) if website else None,
             "instagram": "@" + _norm_account(instagram) if instagram else None}
    items.append(entry)
    store.save("watchlist", items)
    return {"added": True, "entry": entry}


def looks_like_launch(text: str) -> bool:
    return bool(LAUNCH_WORDS.search(text))


def new_posts() -> list[tuple[dict, dict]]:
    """(post, watchlist entry) for watched accounts not yet processed."""
    seen = set(store.load("monitor_seen"))
    index = {}
    for w in watchlist():
        for key in (w.get("website"), w.get("instagram")):
            if key:
                index[_norm_account(key)] = w
    out = []
    for post in store.load("launch_feed"):
        entry = index.get(_norm_account(post["account"]))
        if entry and post["id"] not in seen:
            out.append((post, entry))
    return out


def mark_seen(post_ids: list[str]) -> None:
    seen = store.load("monitor_seen")
    store.save("monitor_seen", sorted(set(seen) | set(post_ids)))


def recent_alerts(ctx: RepContext) -> list[dict]:
    return [m for m in store.load("outbox") if m["rep"] == ctx.rep_id and m["kind"] == "launch"][-10:]
