"""Follow-up tasks and reminders (requirement 5).

Reps only see and change their own tasks. A follow-up tied to a CRM record
requires owning that record, which stops two reps working the same prospect.
Scheduling and completing a follow-up both log an activity on the CRM record.
"""

from datetime import date, timedelta

from .. import store
from ..context import RepContext, rep_names
from . import crm, notify


def _tasks():
    return store.load("tasks")


def _mine(ctx: RepContext, tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if t["rep"] == ctx.rep_id]


def create_task(ctx: RepContext, title: str, due: str, record_id: str | None = None, notes: str = "") -> dict:
    try:
        due_date = date.fromisoformat(due)
    except ValueError:
        return {"created": False, "reason": f"'{due}' isn't a date in YYYY-MM-DD form."}
    if record_id:
        owner = crm.owner_of(record_id)
        if owner is None:
            return {"created": False, "reason": f"No CRM record {record_id}."}
        if owner != ctx.rep_id and not ctx.is_manager:
            return {"created": False,
                    "reason": f"{record_id} is owned by {rep_names().get(owner, owner)}. "
                              "Follow-ups on another rep's record would mean conflicting outreach."}
    tasks = _tasks()
    task = {"id": store.next_id("TASK", tasks), "rep": ctx.rep_id, "record_id": record_id,
            "title": title, "due": due_date.isoformat(), "status": "open", "notes": notes}
    tasks.append(task)
    store.save("tasks", tasks)
    if record_id:
        crm.log_activity(ctx, record_id, "Follow-up scheduled", f"{title} (due {task['due']})")
    return {"created": True, "task": task}


def list_tasks(ctx: RepContext, which: str = "open", days_ahead: int = 7) -> dict:
    today = ctx.today
    tasks = [t for t in _mine(ctx, _tasks()) if t["status"] == "open"]
    if which == "overdue":
        tasks = [t for t in tasks if t["due"] < today.isoformat()]
    elif which == "upcoming":
        end = (today + timedelta(days=days_ahead)).isoformat()
        tasks = [t for t in tasks if today.isoformat() <= t["due"] <= end]
    tasks = sorted(tasks, key=lambda t: t["due"])
    for t in tasks:
        t["overdue"] = t["due"] < today.isoformat()
    return {"today": today.isoformat(), "filter": which, "tasks": tasks}


def _find_mine(ctx: RepContext, tasks: list[dict], task_id: str) -> dict | None:
    return next((t for t in _mine(ctx, tasks) if t["id"] == task_id), None)


def complete_task(ctx: RepContext, task_id: str, outcome: str) -> dict:
    tasks = _tasks()
    task = _find_mine(ctx, tasks, task_id)
    if task is None:
        return {"completed": False, "reason": f"You have no task {task_id}."}
    task.update(status="done", outcome=outcome, completed=ctx.today.isoformat())
    store.save("tasks", tasks)
    logged = None
    if task["record_id"]:
        logged = crm.log_activity(ctx, task["record_id"], "Follow-up completed", f"{task['title']}: {outcome}")
    return {"completed": True, "task": task, "crm_activity": logged}


def reschedule_task(ctx: RepContext, task_id: str, new_due: str) -> dict:
    try:
        due_date = date.fromisoformat(new_due)
    except ValueError:
        return {"rescheduled": False, "reason": f"'{new_due}' isn't a date in YYYY-MM-DD form."}
    tasks = _tasks()
    task = _find_mine(ctx, tasks, task_id)
    if task is None:
        return {"rescheduled": False, "reason": f"You have no task {task_id}."}
    task["due"] = due_date.isoformat()
    store.save("tasks", tasks)
    return {"rescheduled": True, "task": task}


def send_due_reminders(today: date | None = None) -> list[dict]:
    """Background job: one Teams message per rep listing what's due today or overdue."""
    today = today or date.today()
    by_rep: dict[str, list[dict]] = {}
    for t in _tasks():
        if t["status"] == "open" and t["due"] <= today.isoformat():
            by_rep.setdefault(t["rep"], []).append(t)
    sent = []
    for rep, tasks in by_rep.items():
        lines = []
        for t in sorted(tasks, key=lambda t: t["due"]):
            when = "today" if t["due"] == today.isoformat() else f"overdue since {t['due']}"
            ref = f" [{t['record_id']}]" if t["record_id"] else ""
            lines.append(f"- {t['title']}{ref}: {when} ({t['id']})")
        sent.append(notify.send(rep, "reminder", "Follow-ups due:\n" + "\n".join(lines)))
    return sent
