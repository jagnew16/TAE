"""Market Intel agent: BDSA research to find and prioritize target accounts (requirement 3)."""

from typing import Literal

from agents import Agent, RunContextWrapper, function_tool

from ..config import MODEL
from ..context import RepContext
from ..services import bdsa, crm


def _crm_flag(ctx: RepContext, brand: str) -> dict:
    check = crm.check_prospect(ctx, brand)
    if check["verdict"] == "no_match":
        return {"crm": "Not in CRM", "ok_to_prospect": True}
    m = check["matches"][0]
    label = f"{'Customer' if m['is_customer'] else m['record_type'].title()} ({m['status']}), owner {m['owner']}"
    own_prospect = not m["is_customer"] and m["owner_id"] == ctx.rep_id
    return {"crm": label, "ok_to_prospect": own_prospect}


@function_tool
def top_brands(ctx: RunContextWrapper[RepContext], state: str, top_n: int = 10,
               period: Literal["month", "quarter", "year"] = "month") -> dict:
    """Rank the top brands in a state by sales revenue, each flagged with its CRM status.

    Args:
        state: Two-letter state code, e.g. "CA".
        top_n: How many brands to return (10, 20, 30, or 50 are typical).
        period: Revenue window: latest month, latest quarter, or trailing year.
    """
    result = bdsa.top_brands(state, top_n, period)
    for row in result["brands"]:
        row.update(_crm_flag(ctx.context, row["brand"]))
    return result


@function_tool
def brand_detail(brand: str, state: str) -> dict:
    """Monthly/quarterly/annual revenue, rankings, and products for one brand in one state.

    Args:
        brand: Brand name as BDSA lists it.
        state: Two-letter state code.
    """
    return bdsa.brand_detail(brand, state)


@function_tool
def category_trends(state: str) -> dict:
    """Product category market share and quarter-over-quarter growth in a state.

    Args:
        state: Two-letter state code.
    """
    return bdsa.category_trends(state)


@function_tool
def top_products(state: str, category: str | None = None, top_n: int = 10) -> dict:
    """Best-selling products in a state, optionally within one category.

    Args:
        state: Two-letter state code.
        category: Optional category: Flower, Vape, Pre-Rolls, Edibles, Concentrates, Beverages, Topicals.
        top_n: How many products to return.
    """
    return bdsa.top_products(state, category, top_n)


@function_tool
def list_states() -> list[str]:
    """States with BDSA coverage."""
    return bdsa.available_states()


INSTRUCTIONS = """\
You are the market intelligence specialist inside AAA, a sales assistant for sales reps.
You answer with BDSA market data only. Never invent figures.

- Use the tools for every number. If a state or brand isn't covered, say so.
- Always state the period the numbers cover (e.g. "Jul to Sep 2026") and that the source is BDSA.
- top_brands flags each brand's CRM status. When the rep is looking for prospects, put
  `ok_to_prospect: false` brands in a separate "Already in CRM" list with who owns them.
  Existing customers are never new prospects.
- When asked to prioritize, weigh revenue, growth, and rank change, and say why in one line per brand.
- Format revenue as $1.2M / $340K. Keep tables compact.
"""

market_intel_agent = Agent[RepContext](
    name="Market Intel",
    instructions=INSTRUCTIONS,
    tools=[top_brands, brand_detail, category_trends, top_products, list_states],
    model=MODEL,
)
