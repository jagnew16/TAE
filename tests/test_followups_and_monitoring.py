import asyncio

from aaa import store
from aaa.jobs import run_monitor
from aaa.services import followups, monitor, notify

from .conftest import TODAY


def test_cannot_schedule_followups_on_another_reps_record(alice):
    result = followups.create_task(alice, "Call them", "2026-10-10", record_id="LEAD-2002")
    assert result["created"] is False and "Ben Okafor" in result["reason"]


def test_followup_lifecycle_logs_to_crm(alice):
    created = followups.create_task(alice, "Send pricing", "2026-10-08", record_id="ACC-1004")
    task_id = created["task"]["id"]
    done = followups.complete_task(alice, task_id, "Sent pricing; decision by Friday")
    assert done["completed"] and done["crm_activity"]["logged"]
    types = [a["type"] for a in store.load("crm")["activities"] if a["record_id"] == "ACC-1004"]
    assert "Follow-up scheduled" in types and "Follow-up completed" in types


def test_reps_only_see_and_change_their_own_tasks(alice, ben):
    assert all(t["rep"] == "alice" for t in followups.list_tasks(alice)["tasks"])
    bens_task = followups.list_tasks(ben)["tasks"][0]["id"]
    assert followups.complete_task(alice, bens_task, "done")["completed"] is False


def test_overdue_filter(alice):
    followups.create_task(alice, "Late thing", "2026-10-01")
    overdue = followups.list_tasks(alice, "overdue")["tasks"]
    assert overdue and all(t["due"] < TODAY.isoformat() for t in overdue)


def test_bad_date_is_rejected(alice):
    assert followups.create_task(alice, "x", "next tuesday")["created"] is False


def test_reminders_go_to_each_rep_privately(alice, ben):
    followups.create_task(alice, "Due today", TODAY.isoformat())
    sent = followups.send_due_reminders(TODAY)
    assert "alice" in {m["rep"] for m in sent}
    alices = notify.deliver("alice")
    assert alices and all(m["rep"] == "alice" for m in alices)
    assert notify.deliver("alice") == []  # delivered once


def test_monitor_alerts_owner_once_per_company_and_skips_non_launches():
    result = asyncio.run(run_monitor(use_llm=False))
    companies = [a["text"].split(":")[0] for a in result["alerts"]]
    assert len(companies) == len(set(companies))
    assert all("hiring" not in a["text"].lower() for a in result["alerts"])
    # Ember Labs is Ben's lead, so its launch goes to Ben, not Alice.
    ember = [a for a in result["alerts"] if "Ember Labs" in a["text"]]
    assert ember and all(a["rep"] == "ben" for a in ember)
    # Nothing new on a second run.
    assert asyncio.run(run_monitor(use_llm=False))["alerts"] == []


def test_unwatched_brands_are_ignored():
    watched = {w["company"] for w in monitor.watchlist()}
    alerts = asyncio.run(run_monitor(use_llm=False))["alerts"]
    assert all(any(c in a["text"] for c in watched) for a in alerts)


def test_watch_requires_owning_the_record(alice):
    assert monitor.add(alice, "LEAD-2002", instagram="@emberlabs")["added"] is False
    assert monitor.add(alice, "ACC-1004", website="maplewoodfarms.example")["added"] is True


def test_launch_keyword_filter():
    assert monitor.looks_like_launch("Introducing our new seltzer line")
    assert not monitor.looks_like_launch("We're hiring a cultivation lead")
