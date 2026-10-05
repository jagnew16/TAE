"""Launch Monitor: the chat-side agent for managing watches, plus the classifier the
background job uses to confirm and summarize detected launches (requirement 6)."""

from pydantic import BaseModel

from agents import Agent, RunContextWrapper, function_tool

from ..config import MODEL
from ..context import RepContext
from ..services import monitor


@function_tool
def watch_company(ctx: RunContextWrapper[RepContext], record_id: str,
                  website: str | None = None, instagram: str | None = None) -> dict:
    """Start monitoring a company's website and/or Instagram for product launches.
    The rep must own the CRM record. Alerts go to the record's owner.

    Args:
        record_id: CRM account or lead ID.
        website: Website domain, e.g. brand.com.
        instagram: Instagram handle, e.g. @brand.
    """
    return monitor.add(ctx.context, record_id, website, instagram)


@function_tool
def list_watches(ctx: RunContextWrapper[RepContext]) -> list[dict]:
    """Companies being monitored on records the rep owns."""
    return monitor.my_watchlist(ctx.context)


@function_tool
def recent_launch_alerts(ctx: RunContextWrapper[RepContext]) -> list[dict]:
    """The rep's most recent launch alerts."""
    return monitor.recent_alerts(ctx.context)


INSTRUCTIONS = """\
You are the launch monitoring specialist inside AAA. You manage which customer and prospect
websites and Instagram accounts are watched for new product launches, and you report recent alerts.
To add a watch you need the CRM record ID. If you don't have it, say the CRM specialist can look it up.
Monitoring runs on a schedule; alerts arrive in the rep's Teams chat.
"""

launch_monitor_agent = Agent[RepContext](
    name="Launch Monitor",
    instructions=INSTRUCTIONS,
    tools=[watch_company, list_watches, recent_launch_alerts],
    model=MODEL,
)


class LaunchAssessment(BaseModel):
    is_product_launch: bool
    product: str | None
    summary: str  # one sentence a rep can read in a notification


launch_classifier = Agent(
    name="Launch Classifier",
    instructions=(
        "You read one website or Instagram post from a cannabis brand. Decide whether it announces a "
        "new product, product line, flavor, or format now or soon available. Hiring posts, events, "
        "thank-yous, and restocks of existing products are not launches. If it is a launch, name the "
        "product and write a one-sentence summary for a sales rep. Use only what the post says."
    ),
    output_type=LaunchAssessment,
    model=MODEL,
)
