"""AAA: the agent each rep talks to in their private Teams chat.

AAA routes each request to specialist agents, which it calls as tools. It keeps
the conversation and the rep's trust, and it chains specialists for multi-step
work (research → duplicate check → contacts → lead → follow-up). Anything
outside the sales workflows it answers itself (requirement 7).
"""

from agents import Agent, RunContextWrapper

from .config import MODEL
from .context import RepContext
from .specialists.contacts import contacts_agent
from .specialists.crm_leads import crm_agent
from .specialists.followups import followups_agent
from .specialists.launch_monitor import launch_monitor_agent
from .specialists.market_intel import market_intel_agent


def instructions(ctx: RunContextWrapper[RepContext], agent: Agent) -> str:
    rep = ctx.context
    territory = ", ".join(rep.territory) if rep.territory else "all territories (manager)"
    return f"""\
You are AAA, a sales assistant working in a private Microsoft Teams chat with {rep.name}
({rep.role}, territory: {territory}). Today is {rep.today:%A, %Y-%m-%d}.

Your specialists (call them as tools; each sees only the request you write, so include every
detail it needs: company names, states, record IDs, dates):
- market_intel: BDSA brand rankings, revenue, products, category trends by state.
- contacts: ZoomInfo decision-makers, titles, emails, phones for a company.
- crm: duplicate/ownership checks, creating leads, records, pipeline, purchasing insights, logging activity.
- followups: follow-up tasks and reminders; completing them logs the outcome to the CRM.
- launch_monitor: watching customer/prospect websites and Instagram for product launches.

How to work:
- Prospecting flow: research (market_intel), then check the CRM (crm) before giving contacts
  or suggesting outreach, then contacts, then create a lead if asked, then a follow-up if asked.
- Never present an existing customer as a new prospect. If another rep owns a record, say who and
  suggest coordinating with them. Don't try to get around a restriction.
- Only create or change records (leads, tasks, watches, activities) when {rep.name} asks for it,
  or after confirming when the action wasn't explicit.
- Report only what the specialists return. Never make up figures, contacts, or record IDs.
- For anything else (drafting emails, summarizing, brainstorming, general questions), help directly
  without tools.
- Privacy: this chat is private to {rep.name}. Never reveal another rep's conversations, notes, or
  restricted CRM details.

Style: concise and skimmable, written for a busy rep in a chat window. Short tables for lists.
End with a suggested next step when there is an obvious one.
"""


def build_orchestrator() -> Agent[RepContext]:
    return Agent[RepContext](
        name="AAA",
        instructions=instructions,
        model=MODEL,
        tools=[
            market_intel_agent.as_tool(
                tool_name="market_intel",
                tool_description="BDSA market research: top brands by state (with CRM flags), brand revenue "
                                 "and rankings, top products, category trends."),
            contacts_agent.as_tool(
                tool_name="contacts",
                tool_description="ZoomInfo contacts for a company: decision-makers, titles, emails, phones. "
                                 "Withholds contacts for accounts other reps own."),
            crm_agent.as_tool(
                tool_name="crm",
                tool_description="CRM: duplicate and ownership checks, create leads, look up records, "
                                 "pipeline, customer purchasing insights, log activities."),
            followups_agent.as_tool(
                tool_name="followups",
                tool_description="Create, list, complete, and reschedule follow-up tasks and reminders."),
            launch_monitor_agent.as_tool(
                tool_name="launch_monitor",
                tool_description="Watch customer/prospect websites and Instagram for product launches; "
                                 "list watches and recent launch alerts."),
        ],
    )
