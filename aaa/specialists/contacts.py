"""Contacts agent: ZoomInfo decision-maker lookup for target accounts (requirement 3)."""

from agents import Agent, RunContextWrapper, function_tool

from ..config import MODEL
from ..context import RepContext
from ..services import crm, zoominfo


def lookup_contacts(rep: RepContext, company: str, title_keywords: list[str] | None = None) -> dict:
    company_info = zoominfo.find_company(company)
    check = crm.check_prospect(rep, company, company_info["domain"] if company_info else None)
    blocking = [m for m in check["matches"] if not rep.can_see(m["owner_id"])]
    if blocking:
        m = blocking[0]
        return {
            "withheld": True,
            "reason": (f"{m['name']} is {'a customer' if m['is_customer'] else 'a ' + m['record_type']} "
                       f"owned by {m['owner']} ({m['status']}). Contact details are withheld to avoid "
                       f"conflicting outreach; coordinate with {m['owner']}."),
        }
    result = zoominfo.find_contacts(company, title_keywords)
    result["crm_check"] = {"verdict": check["verdict"], "guidance": check["guidance"]}
    return result


@function_tool
def find_contacts(ctx: RunContextWrapper[RepContext], company: str,
                  title_keywords: list[str] | None = None) -> dict:
    """Find decision-makers at a company: names, titles, business emails, phones.

    Checks the CRM first. If another rep owns the company, or it's an existing
    customer the requesting rep doesn't own, contacts are withheld to prevent
    conflicting outreach.

    Args:
        company: Company or brand name.
        title_keywords: Optional title filters, e.g. ["procurement", "operations"].
    """
    return lookup_contacts(ctx.context, company, title_keywords)


INSTRUCTIONS = """\
You are the contact discovery specialist inside AAA. You find the right people to reach at
target accounts using ZoomInfo.

- Use find_contacts for every lookup. Never invent names, emails, or phone numbers.
- Lead with the most relevant decision-makers for buying packaging and supplies:
  procurement, purchasing, operations, supply chain, then executives.
- If the result is withheld, explain why and who owns the account. Don't try to work around it.
- If the CRM check says existing customer or existing record, repeat that guidance plainly.
- Present contacts as a short table: name, title, email, phone.
"""

contacts_agent = Agent[RepContext](
    name="Contacts",
    instructions=INSTRUCTIONS,
    tools=[find_contacts],
    model=MODEL,
)
