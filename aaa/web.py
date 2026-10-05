"""Web app: serves the dashboard (index.html) and the JSON API behind it.

  python -m aaa serve        # then open http://127.0.0.1:8000/?rep=alice

The data pages call the same services the agents' tools use, so they follow the
same rules (a rep sees only their own tasks, alerts, and records). "Ask AAA" runs
the real orchestrator.

Identity: the page sends `rep=<id>` as a stand-in for sign-in. In Teams, the rep
comes from the signed-in user's token instead, and the client can't choose it.
"""

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config, conversation, store
from .context import RepContext, load_rep
from .jobs import run_monitor
from .services import bdsa, crm, followups
from .specialists.market_intel import _crm_flag

INDEX = Path(__file__).resolve().parent.parent / "index.html"


def chat_enabled() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Process any launch posts not yet seen so the Launch Monitor page has alerts.
    # Uses the classifier agent when there's an API key, the keyword filter otherwise.
    await run_monitor(use_llm=chat_enabled())
    yield


app = FastAPI(title="AAA", lifespan=lifespan)


def rep_ctx(rep: str) -> RepContext:
    try:
        return load_rep(rep)
    except ValueError as e:
        raise HTTPException(404, str(e))


def due_label(due: str, today: date) -> tuple[str, bool]:
    d = date.fromisoformat(due)
    days = (d - today).days
    if days < 0:
        return f"{-days} day{'s' if days < -1 else ''} overdue", True
    if days == 0:
        return "Today", False
    if days == 1:
        return "Tomorrow", False
    return f"{d:%b} {d.day}", False


def open_tasks(ctx: RepContext) -> list[dict]:
    """The rep's open tasks, overdue first, with the CRM record's name attached."""
    tasks = followups.list_tasks(ctx)["tasks"]
    for t in tasks:
        record = crm.get_record(ctx, t["record_id"]) if t["record_id"] else None
        t["record_name"] = record["name"] if record else None
        t["due_label"], t["overdue"] = due_label(t["due"], ctx.today)
    return tasks


def launch_alerts(ctx: RepContext) -> list[dict]:
    alerts = [m for m in store.load("outbox") if m["rep"] == ctx.rep_id and m["kind"] == "launch"]
    return sorted(alerts, key=lambda m: m.get("data", {}).get("observed_at", ""), reverse=True)


def customer_insights(ctx: RepContext) -> list[dict]:
    out = []
    for acc in crm.my_pipeline(ctx)["accounts"]:
        if acc["is_customer"]:
            insight = crm.account_insights(ctx, acc["id"])
            if "categories" in insight:
                out.append(insight | {"id": acc["id"]})
    return out


def recommendation(insights: list[dict]) -> dict | None:
    """The customer with the most to gain: declining orders and/or a whitespace gap."""
    def score(i):
        gap = i["whitespace"][0]["last_quarter_revenue"] if i["whitespace"] else 0
        return gap / 1e6 + max(0, -(i["total_change_pct"] or 0))
    candidates = [i for i in insights if i["whitespace"] or (i["total_change_pct"] or 0) < 0]
    if not candidates:
        return None
    best = max(candidates, key=score)
    parts = []
    if (best["total_change_pct"] or 0) < 0:
        worst = min(best["categories"], key=lambda c: c["change_pct"] if c["change_pct"] is not None else 0)
        parts.append(f"Orders are down {abs(best['total_change_pct'])}% over the last quarter, "
                     f"led by {worst['category'].lower()}.")
    if best["whitespace"]:
        g = best["whitespace"][0]
        growth = f", {g['qoq_growth_pct']:+}% quarter over quarter" if g["qoq_growth_pct"] is not None else ""
        parts.append(f"It sells ${g['last_quarter_revenue'] / 1e6:.1f}M of {g['brand_sells'].lower()} a quarter "
                     f"at retail{growth}, but buys no {g['we_could_supply'].lower()} from you.")
    gap = best["whitespace"][0]["we_could_supply"].lower() if best["whitespace"] else None
    prompt = (f"Prepare outreach for {best['account']} ({best['id']}). "
              + (f"Pitch {gap}. " if gap else "Their orders are declining. ")
              + "Find the right contact and draft a short email.")
    return {"account": best["account"], "id": best["id"], "headline": f"Start with {best['account']}",
            "body": " ".join(parts), "prompt": prompt}


@app.get("/")
def index():
    return FileResponse(INDEX)


@app.get("/api/status")
def status():
    return {"chat_enabled": chat_enabled(), "model": config.MODEL or "Agents SDK default"}


@app.get("/api/reps")
def reps():
    return store.load("reps")


@app.get("/api/dashboard")
def dashboard(rep: str):
    ctx = rep_ctx(rep)
    tasks = open_tasks(ctx)
    alerts = launch_alerts(ctx)
    insights = customer_insights(ctx)
    week_end = (ctx.today + timedelta(days=7)).isoformat()

    attention = []
    for i in sorted(insights, key=lambda i: i["total_change_pct"] or 0):
        lapsed = [c for c in i["categories"] if c["lapsed"]]
        declining = (i["total_change_pct"] or 0) <= -5
        if not (lapsed or declining):
            continue
        title = (f"{i['account']} · stopped ordering {lapsed[0]['category'].lower()}" if lapsed
                 else f"{i['account']} · orders down {abs(i['total_change_pct'])}%")
        details = []
        if lapsed:
            details.append(f"No orders since {lapsed[0]['last_order_month']}.")
        if declining and lapsed:
            details.append(f"Total orders down {abs(i['total_change_pct'])}%.")
        details.append("AAA found a cross-sell opportunity." if i["whitespace"] else "Worth a check-in.")
        attention.append({"level": "red", "title": title, "detail": " ".join(details),
                          "action": "review", "record_id": i["id"], "account": i["account"]})
    for t in tasks:
        if t["due"] <= (ctx.today + timedelta(days=1)).isoformat():
            attention.append({"level": "amber", "title": t["title"],
                              "detail": f"{t['record_name'] or 'No record'} · {t['due_label'].lower()}",
                              "action": "complete", "task_id": t["id"]})
    if alerts:
        a = alerts[0]["data"]
        attention.append({"level": "cyan", "title": f"{a['company']} launched a new product",
                          "detail": f"{a.get('product') or 'New product'} · detected {a['observed_at'][:10]}",
                          "action": "launches"})

    return {
        "rep": {"id": ctx.rep_id, "name": ctx.name, "role": ctx.role, "territory": ctx.territory},
        "today": ctx.today.isoformat(),
        "attention": attention,
        "metrics": {"overdue": sum(t["overdue"] for t in tasks),
                    "due_this_week": sum(ctx.today.isoformat() <= t["due"] <= week_end for t in tasks),
                    "launch_alerts": len(alerts)},
        "recommendation": recommendation(insights),
        "tasks": tasks[:4],
        "launches": alerts[:3],
    }


@app.get("/api/pipeline")
def pipeline(rep: str):
    ctx = rep_ctx(rep)
    tasks = open_tasks(ctx)
    declining = {i["id"] for i in customer_insights(ctx) if (i["total_change_pct"] or 0) <= -5
                 or any(c["lapsed"] for c in i["categories"])}
    rows = []
    data = crm.my_pipeline(ctx)
    for r in data["accounts"] + data["leads"]:
        next_task = next((t for t in tasks if t["record_id"] == r["id"]), None)
        rows.append(r | {
            "kind": "Customer" if r["is_customer"] else r["record_type"].title(),
            "next_task": next_task,
            "needs_attention": r["id"] in declining or bool(next_task and next_task["due"] <= ctx.today.isoformat()),
        })
    return {"records": rows}


@app.get("/api/market")
def market(rep: str, state: str | None = None, period: Literal["month", "quarter", "year"] = "quarter",
           top_n: int = 10):
    ctx = rep_ctx(rep)
    state = (state or (ctx.territory[0] if ctx.territory else "CA")).upper()
    try:
        result = bdsa.top_brands(state, top_n, period)
    except ValueError as e:
        raise HTTPException(404, str(e))
    for row in result["brands"]:
        row.update(_crm_flag(ctx, row["brand"]))
        if row["ok_to_prospect"] and row["crm"] == "Not in CRM":
            row["action"], row["tone"] = "prospect", "new"
        elif row["ok_to_prospect"]:
            row["action"], row["tone"] = "continue", "working"
        elif row["crm"].startswith("Customer"):
            row["action"], row["tone"] = "customer", "customer"
        else:
            row["action"], row["tone"] = "coordinate", "blocked"
    result["states"] = bdsa.available_states()
    result["trends"] = bdsa.category_trends(state)["categories"]
    return result


@app.get("/api/tasks")
def tasks(rep: str):
    return {"tasks": open_tasks(rep_ctx(rep))}


class CompleteIn(BaseModel):
    rep: str
    outcome: str = "Done"


@app.post("/api/tasks/{task_id}/complete")
def complete(task_id: str, body: CompleteIn):
    result = followups.complete_task(rep_ctx(body.rep), task_id, body.outcome or "Done")
    if not result["completed"]:
        raise HTTPException(404, result["reason"])
    return result


@app.get("/api/launches")
def launches(rep: str):
    return {"alerts": launch_alerts(rep_ctx(rep))}


class ChatIn(BaseModel):
    rep: str
    message: str


@app.post("/api/chat")
async def chat(body: ChatIn):
    ctx = rep_ctx(body.rep)
    if not chat_enabled():
        raise HTTPException(503, "Ask AAA needs an OpenAI API key. Add OPENAI_API_KEY to .env and restart "
                                 "the server. Every other page works without one.")
    try:
        reply, used = await conversation.ask(ctx, body.message)
    except Exception as e:  # surface model/API errors in the chat instead of a blank failure
        raise HTTPException(502, f"AAA couldn't reach the model: {e}")
    return {"reply": reply, "used": used}
