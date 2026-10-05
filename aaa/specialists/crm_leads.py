"""CRM & Leads agent: duplicate checks, lead creation, ownership, sales insights (requirement 4)."""

from agents import Agent, RunContextWrapper, function_tool

from ..config import MODEL
from ..context import RepContext
from ..services import crm


@function_tool
def check_prospect(ctx: RunContextWrapper[RepContext], company: str, website: str | None = None) -> dict:
    """Check whether a company already exists as a customer, account, contact, or lead.

    Returns a verdict (existing_customer, existing_record, no_match), guidance, and
    the matching records with status and owner.

    Args:
        company: Company or brand name.
        website: Optional website domain, which makes the match more reliable.
    """
    return crm.check_prospect(ctx.context, company, website)


@function_tool
def create_lead(ctx: RunContextWrapper[RepContext], company: str, state: str,
                website: str | None = None, contact_name: str | None = None,
                contact_title: str | None = None, contact_email: str | None = None,
                contact_phone: str | None = None) -> dict:
    """Create a new CRM lead. Runs the duplicate check itself and refuses if a record exists.
    Ownership is assigned by territory.

    Args:
        company: Company name.
        state: Two-letter state code where the company operates.
        website: Company website domain.
        contact_name: Primary contact's name.
        contact_title: Primary contact's job title.
        contact_email: Primary contact's business email.
        contact_phone: Primary contact's phone.
    """
    return crm.create_lead(ctx.context, company, state, website, contact_name, contact_title,
                           contact_email, contact_phone)


@function_tool
def get_record(ctx: RunContextWrapper[RepContext], record_id: str) -> dict:
    """Look up a CRM account or lead by ID (e.g. ACC-1001, LEAD-2001).

    Args:
        record_id: The record ID.
    """
    return crm.get_record(ctx.context, record_id) or {"error": f"No record {record_id}."}


@function_tool
def my_pipeline(ctx: RunContextWrapper[RepContext]) -> dict:
    """The requesting rep's own accounts and leads with status."""
    return crm.my_pipeline(ctx.context)


@function_tool
def account_insights(ctx: RunContextWrapper[RepContext], account_id: str) -> dict:
    """Purchasing patterns for a customer: spend by category, quarter-over-quarter change,
    lapsed categories, and whitespace (categories the brand sells that it doesn't buy from us).
    Only works for accounts the rep owns.

    Args:
        account_id: Account ID, e.g. ACC-1001.
    """
    return crm.account_insights(ctx.context, account_id)


@function_tool
def log_activity(ctx: RunContextWrapper[RepContext], record_id: str, activity_type: str, summary: str) -> dict:
    """Record a call, email, meeting, or note on a CRM record the rep owns.

    Args:
        record_id: Account or lead ID.
        activity_type: e.g. Call, Email, Meeting, Note.
        summary: One or two sentences on what happened.
    """
    return crm.log_activity(ctx.context, record_id, activity_type, summary)


INSTRUCTIONS = """\
You are the CRM specialist inside AAA. You keep the CRM clean and prevent reps from colliding.

Before any new lead or outreach, run check_prospect, then follow the verdict:
1. existing_customer: tell the rep it's a customer and who owns it. It is excluded from
   new-prospect outreach. Do not create a lead.
2. existing_record: show each match's status and owner. If another rep owns it, tell the rep to
   coordinate with that owner. If the rep owns it, point them to the existing record.
3. no_match: create the lead with create_lead if the rep asked for it, then report the
   lead ID and owner. If the lead was assigned to another rep by territory, say so.

Other rules:
- Only create or change records when the rep asked you to.
- Restricted records show only status and owner. Don't speculate about hidden details.
- For sales insights, use account_insights and my_pipeline. Call out growth, decline, and
  lapsed categories. `whitespace` lists categories the brand sells at retail but buys no
  packaging for from us: those are cross-sell opportunities, biggest and fastest-growing first.
  End with concrete next steps.
"""

crm_agent = Agent[RepContext](
    name="CRM & Leads",
    instructions=INSTRUCTIONS,
    tools=[check_prospect, create_lead, get_record, my_pipeline, account_insights, log_activity],
    model=MODEL,
)
