"""BDSA market data: brand rankings, revenue, products, and category trends by state.

Reads the mock dataset in aaa/seed/bdsa.json. A real integration would call
BDSA's API with the same inputs; the outputs here are shaped like that.
"""

from collections import defaultdict

from .. import store

PERIOD_MONTHS = {"month": 1, "quarter": 3, "year": 12}


def _data():
    return store.load("bdsa")


def _state(data, state: str) -> list[dict]:
    state = state.upper()
    if state not in data["states"]:
        raise ValueError(f"No BDSA data for {state}. Available: {', '.join(data['states'])}")
    return data["states"][state]["brands"]


def _window(series: list[float], months: int, offset: int = 0) -> float:
    end = len(series) - offset
    return sum(series[max(0, end - months):end])


def _brand_series(brand: dict) -> list[float]:
    return [sum(vals) for vals in zip(*(p["monthly_revenue"] for p in brand["products"]))]


def _rank(brands: list[dict], months: int, offset: int = 0) -> list[tuple[dict, float]]:
    scored = [(b, _window(_brand_series(b), months, offset)) for b in brands]
    return sorted(scored, key=lambda x: x[1], reverse=True)


def available_states() -> list[str]:
    return list(_data()["states"])


def top_brands(state: str, top_n: int = 10, period: str = "month") -> dict:
    data = _data()
    brands = _state(data, state)
    months = PERIOD_MONTHS[period]
    current = _rank(brands, months)
    previous = {b["brand"]: i for i, (b, _) in enumerate(_rank(brands, months, offset=months), start=1)}

    rows = []
    for rank, (b, revenue) in enumerate(current[:top_n], start=1):
        prior = _window(_brand_series(b), months, offset=months)
        cats = defaultdict(float)
        for p in b["products"]:
            cats[p["category"]] += _window(p["monthly_revenue"], months)
        rows.append({
            "rank": rank,
            "brand": b["brand"],
            "revenue": round(revenue),
            "growth_vs_prior_period_pct": round((revenue - prior) / prior * 100, 1) if prior else None,
            "rank_change": previous[b["brand"]] - rank,
            "top_category": max(cats, key=cats.get),
        })
    note = None
    if top_n > len(brands):
        note = f"Only {len(brands)} brands are tracked in {state.upper()}."
    period_label = {"month": data["months"][-1],
                    "quarter": f"{data['months'][-3]} to {data['months'][-1]}",
                    "year": f"{data['months'][0]} to {data['months'][-1]}"}[period]
    return {"state": state.upper(), "period": period, "covering": period_label,
            "source": data["source"], "brands": rows, "note": note}


def brand_detail(brand: str, state: str) -> dict:
    data = _data()
    brands = _state(data, state)
    match = next((b for b in brands if b["brand"].lower() == brand.lower()), None)
    if match is None:
        close = [b["brand"] for b in brands if brand.lower().split()[0] in b["brand"].lower()]
        return {"error": f"{brand} isn't tracked in {state.upper()}.", "did_you_mean": close[:5]}
    series = _brand_series(match)
    ranks = {}
    for label, months in (("month", 1), ("quarter", 3), ("year", 12)):
        ranks[label] = next(i for i, (b, _) in enumerate(_rank(brands, months), start=1) if b is match)
    return {
        "brand": match["brand"], "state": state.upper(),
        "rank": ranks,
        "monthly_revenue": dict(zip(data["months"], (round(v) for v in series))),
        "quarterly_revenue": round(_window(series, 3)),
        "annual_revenue": round(_window(series, 12)),
        "products": sorted(({"name": p["name"], "category": p["category"],
                             "last_quarter_revenue": round(_window(p["monthly_revenue"], 3))}
                            for p in match["products"]),
                           key=lambda p: p["last_quarter_revenue"], reverse=True),
        "other_states": [s for s, d in data["states"].items()
                         if s != state.upper() and any(b["brand"] == match["brand"] for b in d["brands"])],
    }


def category_trends(state: str) -> dict:
    """Category share of the state market and quarter-over-quarter growth."""
    data = _data()
    brands = _state(data, state)
    recent, prior = defaultdict(float), defaultdict(float)
    for b in brands:
        for p in b["products"]:
            recent[p["category"]] += _window(p["monthly_revenue"], 3)
            prior[p["category"]] += _window(p["monthly_revenue"], 3, offset=3)
    total = sum(recent.values())
    rows = [{"category": c,
             "last_quarter_revenue": round(recent[c]),
             "share_pct": round(recent[c] / total * 100, 1),
             "qoq_growth_pct": round((recent[c] - prior[c]) / prior[c] * 100, 1) if prior[c] else None}
            for c in recent]
    return {"state": state.upper(), "covering": f"{data['months'][-3]} to {data['months'][-1]}",
            "categories": sorted(rows, key=lambda r: r["last_quarter_revenue"], reverse=True)}


def brand_categories(brand_matches) -> dict:
    """A brand's retail sales by category across every tracked state.

    `brand_matches` decides whether a BDSA brand name is this brand (CRM names
    carry suffixes like ", Inc." that BDSA's don't).
    """
    recent, prior = defaultdict(float), defaultdict(float)
    for d in _data()["states"].values():
        for b in d["brands"]:
            if brand_matches(b["brand"]):
                for p in b["products"]:
                    recent[p["category"]] += _window(p["monthly_revenue"], 3)
                    prior[p["category"]] += _window(p["monthly_revenue"], 3, offset=3)
    return {c: {"last_quarter_revenue": round(recent[c]),
                "qoq_growth_pct": round((recent[c] - prior[c]) / prior[c] * 100, 1) if prior[c] else None}
            for c in recent}


def top_products(state: str, category: str | None = None, top_n: int = 10) -> dict:
    data = _data()
    rows = []
    for b in _state(data, state):
        for p in b["products"]:
            if category and p["category"].lower() != category.lower():
                continue
            rows.append({"product": p["name"], "brand": b["brand"], "category": p["category"],
                         "last_quarter_revenue": round(_window(p["monthly_revenue"], 3))})
    rows.sort(key=lambda r: r["last_quarter_revenue"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return {"state": state.upper(), "category": category, "products": rows[:top_n]}
