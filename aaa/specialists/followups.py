"""Follow-ups agent: tasks, reminders, and outcomes logged to the CRM (requirement 5)."""

from typing import Literal

from agents import Agent, RunContextWrapper, function_tool

from ..config import MODEL
from ..context import RepContext
from ..services import followups


@function_tool
def create_followup(ctx: RunContextWrapper[RepContext], title: str, due: str,
                    record_id: str | None = None, notes: str = "") -> dict:
    """Schedule a follow-up task. AAA reminds the rep in Teams when it's due.

    Args:
        title: What to do, e.g. "Send pricing to Maya Chen".
        due: Due date, YYYY-MM-DD.
        record_id: CRM account or lead ID it relates to, if any. The rep must own it.
        notes: Optional detail.
    """
    return followups.create_task(ctx.context, title, due, record_id, notes)


@function_tool
def list_followups(ctx: RunContextWrapper[RepContext],
                   which: Literal["open", "overdue", "upcoming"] = "open", days_ahead: int = 7) -> dict:
    """The rep's follow-up tasks.

    Args:
        which: open (all open), overdue, or upcoming (due within days_ahead).
        days_ahead: Window for "upcoming".
    """
    return followups.list_tasks(ctx.context, which, days_ahead)


@function_tool
def complete_followup(ctx: RunContextWrapper[RepContext], task_id: str, outcome: str) -> dict:
    """Mark a follow-up done and record its outcome in the CRM.

    Args:
        task_id: e.g. TASK-5001.
        outcome: What happened, e.g. "Sent pricing; they'll decide by Friday".
    """
    return followups.complete_task(ctx.context, task_id, outcome)


@function_tool
def reschedule_followup(ctx: RunContextWrapper[RepContext], task_id: str, new_due: str) -> dict:
    """Move a follow-up to a new due date.

    Args:
        task_id: e.g. TASK-5001.
        new_due: New due date, YYYY-MM-DD.
    """
    return followups.reschedule_task(ctx.context, task_id, new_due)


def instructions(ctx: RunContextWrapper[RepContext], agent: Agent) -> str:
    return f"""\
You are the follow-up specialist inside AAA. You keep reps on top of next steps.
Today is {ctx.context.today:%A, %Y-%m-%d}. Convert relative dates ("next Tuesday",
"in two weeks") to YYYY-MM-DD yourself and state the date you used.

- Create, complete, or reschedule tasks only when the rep asked you to.
- When completing a task, the outcome goes into the CRM. Capture what actually happened.
- When listing, put overdue items first and show how late they are.
- If a task can't be created because another rep owns the record, explain that and name the owner.
"""


followups_agent = Agent[RepContext](
    name="Follow-ups",
    instructions=instructions,
    tools=[create_followup, list_followups, complete_followup, reschedule_followup],
    model=MODEL,
)
