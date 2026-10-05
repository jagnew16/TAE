"""Generate the mock data AAA runs against.

Every brand, person, domain and number here is fictional. Phone numbers use the
555-01XX range, which is reserved for fiction, and domains end in .example.

The data assumes our company sells packaging and supplies to cannabis brands, so
a brand's BDSA product categories map to the packaging it would buy from us.
Change PACKAGING_FOR if the real product line is different.

Run from the repo root:  python scripts/generate_mock_data.py
Output goes to aaa/seed/. Re-running produces identical files (fixed seed).
"""

import json
import random
import re
from pathlib import Path

rng = random.Random(42)
OUT = Path(__file__).resolve().parent.parent / "aaa" / "seed"

STATES = {"CA": 1.0, "MI": 0.8, "IL": 0.6, "MA": 0.45, "CO": 0.4, "NV": 0.25}
AREA_CODE = {"CA": "213", "MI": "313", "IL": "312", "MA": "617", "CO": "303", "NV": "702"}
MONTHS = [f"{y}-{m:02d}" for y, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 10)]]

# Month-over-month growth by category, so trends are visible in the data.
CATEGORY_TREND = {
    "Beverages": 0.035, "Pre-Rolls": 0.015, "Vape": 0.010, "Edibles": 0.005,
    "Concentrates": 0.0, "Flower": -0.005, "Topicals": -0.010,
}
CATEGORY_WEIGHT = {
    "Flower": 30, "Vape": 25, "Pre-Rolls": 15, "Edibles": 14,
    "Concentrates": 8, "Beverages": 5, "Topicals": 3,
}
PRODUCT_FORMS = {
    "Flower": ["Eighth", "Smalls Quarter", "Reserve Eighth"],
    "Vape": ["Live Resin Cart", "Disposable", "Cured Resin Pod"],
    "Pre-Rolls": ["Infused Pre-Roll", "Pre-Roll 5-Pack", "Mini Dogs 10-Pack"],
    "Edibles": ["Gummies", "Chocolate Bar", "Fast-Acting Chews"],
    "Concentrates": ["Live Rosin", "Badder", "Diamonds"],
    "Beverages": ["Seltzer 4-Pack", "Sparkling Tonic", "Drink Shot"],
    "Topicals": ["Balm", "Relief Lotion", "Bath Soak"],
}
FLAVORS = ["Mango Haze", "Blue Dream", "Lemon Tree", "Watermelon", "Gelato", "Sour Apple",
           "Wild Berry", "Pineapple Express", "Midnight", "Citrus", "Peach", "Huckleberry"]
PACKAGING_FOR = {
    "Flower": "Flower jars & bags", "Vape": "Vape hardware", "Pre-Rolls": "Pre-roll tubes",
    "Edibles": "Edible packaging", "Concentrates": "Concentrate containers",
    "Beverages": "Beverage cans", "Topicals": "Topical jars",
}

NAME_HEADS = ["Amber", "Blue Heron", "Cedar", "Copper", "Desert Bloom", "Ember", "Fernleaf",
              "Golden Coast", "Granite", "Harborlight", "Juniper", "Lakeshore", "Lantern",
              "Maplewood", "Marigold", "North Fork", "Oak & Ash", "Prairie Sky", "Quartz",
              "Riverbend", "Saltwater", "Sierra Pine", "Silver Creek", "Stonefruit",
              "Thistle", "Timberline", "Velvet Hills", "Willowmere", "Yarrow", "Bramble"]
NAME_TAILS = ["Farms", "Botanicals", "Craft Co.", "Extracts", "Collective", "Gardens",
              "Labs", "Provisions", "Supply", "Harvest"]
FIRST = ["Maya", "Jordan", "Priya", "Marcus", "Elena", "Tyler", "Grace", "Andre", "Sofia",
         "Kevin", "Lena", "Omar", "Rachel", "Diego", "Hannah", "Isaac", "Nina", "Caleb",
         "Aisha", "Logan", "Tessa", "Victor", "Mei", "Ryan", "Zoe", "Samir"]
LAST = ["Alvarez", "Brooks", "Chen", "Delgado", "Ellis", "Foster", "Garcia", "Hayes", "Ibarra",
        "Jensen", "Kim", "Lopez", "Mendoza", "Novak", "Okafor", "Patel", "Quinn", "Reyes",
        "Shah", "Turner", "Underwood", "Vasquez", "Whitaker", "Young", "Zimmerman"]
TITLES = ["Co-Founder & CEO", "COO", "VP of Operations", "Director of Procurement",
          "Purchasing Manager", "Head of Brand", "Director of Supply Chain", "Packaging Manager"]


def slug(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def phone(state):
    return f"+1 ({AREA_CODE[state]}) 555-01{rng.randint(0, 99):02d}"


# --- Brands -----------------------------------------------------------------
pool = []
heads = {}
while len(pool) < 140:
    head = rng.choice(NAME_HEADS)
    name = f"{head} {rng.choice(NAME_TAILS)}"
    if name not in heads:
        heads[name] = head
        pool.append(name)

brands = {}
for name in pool:
    cats = rng.sample(list(CATEGORY_WEIGHT), k=rng.choice([1, 2, 2, 3, 3]),
                      counts=list(CATEGORY_WEIGHT.values()))
    cats = list(dict.fromkeys(cats))
    head = heads[name]
    products = []
    for cat in cats:
        for _ in range(rng.choice([1, 1, 2])):
            products.append({"name": f"{head} {rng.choice(FLAVORS)} {rng.choice(PRODUCT_FORMS[cat])}",
                             "category": cat, "share": rng.uniform(0.5, 1.5)})
    brands[name] = {"products": products, "growth": rng.uniform(-0.04, 0.05), "states": []}

# Each state carries 50 brands; many brands sell in more than one state.
bdsa = {"source": "BDSA (mock)", "as_of": MONTHS[-1], "months": MONTHS, "states": {}}
for state, scale in STATES.items():
    picks = rng.sample(pool, 50)
    rows = []
    for rank, name in enumerate(picks, start=1):
        b = brands[name]
        b["states"].append(state)
        base = 9_000_000 * scale * rank ** -0.85
        total_share = sum(p["share"] for p in b["products"])
        products = []
        for p in b["products"]:
            start = base * p["share"] / total_share
            g = b["growth"] + CATEGORY_TREND[p["category"]]
            monthly = []
            for i in range(len(MONTHS)):
                value = start * (1 + g) ** i * rng.uniform(0.95, 1.05)
                monthly.append(round(value, -2))
            products.append({"name": p["name"], "category": p["category"], "monthly_revenue": monthly})
        rows.append({"brand": name, "products": products})
    bdsa["states"][state] = {"brands": rows}

# --- ZoomInfo ---------------------------------------------------------------
zoominfo = {"source": "ZoomInfo (mock)", "companies": []}
for name in pool:
    b = brands[name]
    hq = b["states"][0] if b["states"] else rng.choice(list(STATES))
    b["hq"] = hq
    domain = f"{slug(name)}.example"
    contacts = []
    for title in rng.sample(TITLES, k=rng.choice([2, 3, 4])):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        contacts.append({"name": f"{first} {last}", "title": title,
                         "email": f"{first.lower()}.{last.lower()}@{domain}", "phone": phone(hq)})
    zoominfo["companies"].append({
        "company": name, "domain": domain, "hq_state": hq,
        "employees": rng.choice([12, 25, 40, 60, 85, 120, 200, 350]),
        "instagram": f"@{slug(name)}", "contacts": contacts,
    })
zi_by_name = {c["company"]: c for c in zoominfo["companies"]}

# --- Reps -------------------------------------------------------------------
reps = [
    {"rep_id": "alice", "name": "Alice Moreno", "role": "rep", "territory": ["CA", "NV"]},
    {"rep_id": "ben", "name": "Ben Okafor", "role": "rep", "territory": ["MI", "IL"]},
    {"rep_id": "carla", "name": "Carla Jensen", "role": "rep", "territory": ["CO", "MA"]},
    {"rep_id": "dana", "name": "Dana Whitfield", "role": "manager", "territory": []},
]


# --- CRM --------------------------------------------------------------------
def ranked(state):
    """Brands in a state ranked by last-quarter revenue."""
    rows = bdsa["states"][state]["brands"]
    q = lambda r: sum(sum(p["monthly_revenue"][-3:]) for p in r["products"])
    return [r["brand"] for r in sorted(rows, key=q, reverse=True)]


crm = {"accounts": [], "contacts": [], "leads": [], "activities": [], "orders": []}
taken = set()
acc_n, lead_n, con_n, act_n = 1000, 2000, 3000, 4000


def pick(state, ranks):
    order = [b for b in ranked(state) if b not in taken]
    out = []
    for r in ranks:
        out.append(order[r])
        taken.add(order[r])
    return out


def add_account(name, state, owner, kind, status, display_name=None):
    global acc_n, con_n
    acc_n += 1
    zi = zi_by_name[name]
    acc = {"id": f"ACC-{acc_n}", "name": display_name or name, "state": state, "type": kind,
           "status": status, "owner": owner, "website": zi["domain"],
           "notes": "", "created": "2024-0%d-15" % rng.randint(1, 9)}
    crm["accounts"].append(acc)
    for c in zi["contacts"][:2]:
        con_n += 1
        crm["contacts"].append({"id": f"CON-{con_n}", "account_id": acc["id"], **c})
    return acc


def add_lead(name, state, owner, status, display_name=None):
    global lead_n
    lead_n += 1
    zi = zi_by_name[name]
    c = zi["contacts"][0]
    lead = {"id": f"LEAD-{lead_n}", "company": display_name or name, "state": state, "owner": owner,
            "status": status, "source": rng.choice(["BDSA research", "Trade show", "Referral"]),
            "created": f"2026-0{rng.randint(6, 9)}-{rng.randint(10, 28)}", "website": zi["domain"],
            "contact_name": c["name"], "contact_title": c["title"], "contact_email": c["email"]}
    crm["leads"].append(lead)
    return lead


def add_activity(record_id, rep, kind, summary, date):
    global act_n
    act_n += 1
    crm["activities"].append({"id": f"ACT-{act_n}", "record_id": record_id, "rep": rep,
                              "type": kind, "summary": summary, "date": date})


def add_orders(acc, brand, skip_category=None, trend=0.01, lapse_category=None):
    cats = sorted({p["category"] for p in brands[brand]["products"]})
    if skip_category == "fastest" and len(cats) > 1:
        # Leave out their fastest-growing category: a whitespace opportunity to find.
        skip_category = max(cats, key=CATEGORY_TREND.get)
    for cat in cats:
        if cat == skip_category:
            continue
        base = rng.choice([4000, 6500, 9000, 14000])
        for i, month in enumerate(MONTHS):
            if cat == lapse_category and i >= len(MONTHS) - 3:
                continue
            amount = round(base * (1 + trend) ** i * rng.uniform(0.85, 1.15), -1)
            crm["orders"].append({"account_id": acc["id"], "month": month,
                                  "category": PACKAGING_FOR[cat], "amount": amount})


# Alice (CA/NV): customers include CA's #1 brand, so top-brand lists must flag it.
ca = pick("CA", [0, 3, 8])
a1 = add_account(ca[0], "CA", "alice", "customer", "Active customer", display_name=f"{ca[0]}, Inc.")
add_orders(a1, ca[0], trend=0.02)
a2 = add_account(ca[1], "CA", "alice", "customer", "Active customer")
add_orders(a2, ca[1], trend=-0.03, skip_category="fastest")  # shrinking orders: churn risk
a3 = add_account(ca[2], "CA", "alice", "customer", "Active customer")
add_orders(a3, ca[2], trend=0.01, lapse_category=brands[ca[2]]["products"][0]["category"])
p = pick("CA", [2, 6])
add_account(p[0], "CA", "alice", "prospect", "Working")
add_lead(p[1], "CA", "alice", "Contacted")

# Ben (MI/IL) already owns a lead on a CA top-5 brand, so Alice hits a conflict.
conflict = pick("CA", [0])[0]
add_lead(conflict, "CA", "ben", "Contacted", display_name=f"{conflict} LLC")
mi = pick("MI", [0, 4, 9])
for i, name in enumerate(mi):
    acc = add_account(name, "MI", "ben", "customer", "Active customer")
    add_orders(acc, name, trend=[0.015, 0.0, 0.025][i], skip_category="fastest" if i == 0 else None)
p = pick("IL", [1, 5])
add_account(p[0], "IL", "ben", "prospect", "Nurture")
add_lead(p[1], "IL", "ben", "New")

# Carla (CO/MA)
co = pick("CO", [0, 3])
for name in co:
    acc = add_account(name, "CO", "carla", "customer", "Active customer")
    add_orders(acc, name, trend=0.01, skip_category="fastest")
ma = pick("MA", [1])[0]
acc = add_account(ma, "MA", "carla", "customer", "Active customer")
add_orders(acc, ma, trend=0.03)
p = pick("MA", [3, 7])
add_account(p[0], "MA", "carla", "prospect", "Working")
add_lead(p[1], "MA", "carla", "New")

for rec in crm["accounts"] + crm["leads"]:
    add_activity(rec["id"], rec["owner"], "Call",
                 rng.choice(["Intro call, sent catalog", "Discussed Q4 packaging needs",
                             "Quarterly check-in", "Left voicemail"]),
                 f"2026-09-{rng.randint(1, 26):02d}")

# --- Follow-up tasks (dates relative to the day state is reset) --------------
tasks = []
t_n = 5000
for rec in crm["accounts"] + crm["leads"]:
    if rng.random() < 0.6:
        t_n += 1
        tasks.append({"id": f"TASK-{t_n}", "rep": rec["owner"], "record_id": rec["id"],
                      "title": rng.choice(["Send updated pricing", "Follow up on samples",
                                           "Check in on Q4 order", "Book intro meeting"]),
                      "due_in_days": rng.choice([-5, -2, 0, 1, 3, 7, 14]),
                      "status": "open", "notes": ""})

# --- Launch monitoring --------------------------------------------------------
watched = [a for a in crm["accounts"] if a["type"] == "customer"][:6] + crm["leads"][:2]
watchlist = []
for i, rec in enumerate(watched, start=1):
    name = rec.get("name") or rec.get("company")
    zi = next(c for c in zoominfo["companies"] if c["domain"] == rec["website"])
    watchlist.append({"id": f"WATCH-{i}", "record_id": rec["id"], "company": name,
                      "website": zi["domain"], "instagram": zi["instagram"]})

feed = []
f_n = 0
for w in watchlist:
    zi = next(c for c in zoominfo["companies"] if c["domain"] == w["website"])
    brand = zi["company"]
    cat = rng.choice(list(PRODUCT_FORMS))
    new_product = f"{heads[brand]} {rng.choice(FLAVORS)} {rng.choice(PRODUCT_FORMS[cat])}"
    posts = [
        ("instagram", f"https://instagram.example/{zi['instagram'][1:]}/p/{1000 + f_n}",
         f"Introducing {new_product}! Our newest drop hits shelves this Friday. Available now at "
         f"dispensaries across {zi['hq_state']}. #newproduct #launch"),
        ("website", f"https://{zi['domain']}/news/{slug(new_product)}",
         f"Now available: {new_product}, a new {cat.lower()} product in our lineup."),
        ("instagram", f"https://instagram.example/{zi['instagram'][1:]}/p/{2000 + f_n}",
         rng.choice(["We're hiring! Join our cultivation team.",
                     "Thanks to everyone who stopped by our booth this weekend.",
                     "Happy harvest season from the whole crew."])),
    ]
    for source, url, text in posts[: rng.choice([2, 3])] if rng.random() < 0.7 else posts[2:]:
        f_n += 1
        feed.append({"id": f"FEED-{f_n}", "source": source, "account": zi["instagram"] if source == "instagram" else zi["domain"],
                     "url": url, "text": text, "observed_at": f"2026-10-0{rng.randint(1, 3)}T09:00:00"})
# A launch from a brand nobody is watching should be ignored.
other = next(c for c in zoominfo["companies"] if c["domain"] not in {w["website"] for w in watchlist})
feed.append({"id": f"FEED-{f_n + 1}", "source": "instagram", "account": other["instagram"],
             "url": f"https://instagram.example/{other['instagram'][1:]}/p/9999",
             "text": "Introducing our brand-new seltzer line, launching statewide next week!",
             "observed_at": "2026-10-02T09:00:00"})

# --- Write ------------------------------------------------------------------
OUT.mkdir(parents=True, exist_ok=True)
files = {"catalog": {"packaging_for_category": PACKAGING_FOR}, "bdsa": bdsa, "zoominfo": zoominfo, "reps": reps, "crm": crm, "tasks": tasks,
         "watchlist": watchlist, "launch_feed": feed}
for name, data in files.items():
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote aaa/seed/{name}.json")
