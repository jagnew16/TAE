# Guide to the AAA agents

This file explains the AAA agent prototype to anyone working in this repo: teammates and
AI assistants (ChatGPT, Codex, Claude). Read it before answering questions about the
agents or changing them.

- Requirements: [docs/business-requirements.md](docs/business-requirements.md)
- Full design: [docs/agent-design.md](docs/agent-design.md)

## What AAA is

AAA is an AI sales assistant. Each sales rep chats with it privately (Microsoft Teams in the
final product; a command-line chat for now). It researches prospects with BDSA market data,
finds contacts through ZoomInfo, checks the CRM for duplicates before creating leads, schedules
follow-ups and reminders, and watches customer websites and Instagram for product launches.

The prototype is built on the **OpenAI Agents SDK** (Python) and runs on **fictional mock data**.
No real BDSA, ZoomInfo, CRM, or Teams connection exists yet.

## Current status

| Done | Not done yet |
|---|---|
| All 7 requirements implemented against mock data | Never run against a real OpenAI model (needs an API key) |
| 37 automated tests pass, no API key needed | No Microsoft Teams connection; a CLI chat stands in |
| Agent chain tested end to end with a scripted stand-in model | No real BDSA, ZoomInfo, or CRM APIs |
| Design doc with requirement coverage and open questions | Business rules (territories, manager access) are assumptions to confirm |

## How the agents fit together

One agent, **AAA** (the orchestrator), talks to the rep. It calls five **specialist agents as
tools** and answers general questions (drafting emails, brainstorming) itself.

| Agent | File | What it does | Its tools |
|---|---|---|---|
| AAA | `aaa/orchestrator.py` | Talks to the rep, routes work, chains specialists, answers general questions | the five specialists below |
| Market Intel | `aaa/specialists/market_intel.py` | BDSA research: top 10/20/30/50 brands by state, revenue by month/quarter/year, products, category trends | `top_brands`, `brand_detail`, `category_trends`, `top_products`, `list_states` |
| Contacts | `aaa/specialists/contacts.py` | ZoomInfo decision-makers: names, titles, emails, phones | `find_contacts` |
| CRM & Leads | `aaa/specialists/crm_leads.py` | Duplicate checks, lead creation, ownership, pipeline, customer purchasing insights | `check_prospect`, `create_lead`, `get_record`, `my_pipeline`, `account_insights`, `log_activity` |
| Follow-ups | `aaa/specialists/followups.py` | Follow-up tasks and reminders; outcomes logged to the CRM | `create_followup`, `list_followups`, `complete_followup`, `reschedule_followup` |
| Launch Monitor | `aaa/specialists/launch_monitor.py` | Which websites/Instagram accounts are watched; recent launch alerts | `watch_company`, `list_watches`, `recent_launch_alerts` |
| Launch Classifier | `aaa/specialists/launch_monitor.py` | Used by the background monitor job only: is this post a real product launch? | none (returns structured output) |

Typical prospecting flow: Market Intel (who's worth targeting) → CRM (already a customer, or
owned by another rep?) → Contacts (who to reach) → CRM (create the lead) → Follow-ups (schedule
the next step).

A specialist only sees the request AAA writes for it, not the chat history, so AAA passes along
names, states, record IDs, and dates.

Two scheduled jobs live in `aaa/jobs.py`:
- **Reminders:** one message per rep listing follow-ups due today or overdue.
- **Launch monitor:** new posts from watched accounts → keyword filter → Launch Classifier →
  one alert per company to the account's owner.

## Rules enforced in code (don't move these into prompts)

These are enforced in `aaa/services/`. Prompts only guide the model; the code guarantees the rules.

1. **Identity comes from the signed-in rep, never from the model.** No tool takes a rep ID as
   an argument. Tools read the rep from the run context (`aaa/context.py`). A test fails if a
   tool ever adds a `rep`/`rep_id`/`owner`/`user` parameter.
2. **No duplicate leads.** `create_lead` re-runs the duplicate check itself and refuses on any match.
3. **Another rep's record shows only its status and owner.** Contacts, notes, history, and order
   data are owner-only. Managers see everything.
4. **Contacts are withheld** for companies another rep owns, to prevent conflicting outreach.
5. **Follow-ups and watches only on records you own.**
6. **Each rep sees only their own** tasks, notifications, and chat history.
7. **Name matching ignores Inc/LLC/Co but doesn't merge different companies.** "Ember Labs LLC"
   matches "Ember Labs"; "North Fork Farms" does not match "North Fork Provisions". Website and
   email domains also count as matches.

## Running it

Requires Python 3.10+ and an OpenAI API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # put OPENAI_API_KEY in .env
```

| Command | What it does |
|---|---|
| `python -m aaa reps` | List demo reps |
| `python -m aaa chat --rep alice` | Private chat as Alice |
| `python -m aaa chat --rep alice "your message"` | Send one message and exit |
| `python -m aaa reminders` | Send due/overdue follow-up reminders |
| `python -m aaa monitor` | Check watched accounts for launches (`--no-llm` skips model calls) |
| `python -m aaa reset` | Restore all demo data |
| `pytest` | Run the tests (no API key needed) |

Notifications from the jobs appear when that rep next opens their chat, the way Teams would show them.

## Demo data

All brands, people, emails, and phone numbers are fictional. The data assumes **our company sells
packaging and supplies to cannabis brands** (BDSA is cannabis market data). Each BDSA product
category maps to a packaging line in `aaa/seed/catalog.json`.

**Reps**

| ID | Name | Role | Territory |
|---|---|---|---|
| `alice` | Alice Moreno | rep | CA, NV |
| `ben` | Ben Okafor | rep | MI, IL |
| `carla` | Carla Jensen | rep | CO, MA |
| `dana` | Dana Whitfield | manager | all (sees every record) |

**Records worth knowing (Alice's view)**

| Record | What it shows |
|---|---|
| ACC-1001 Sierra Pine Supply | CA's #1 brand and Alice's customer, so it's excluded from her prospect lists |
| LEAD-2002 Ember Labs | CA's #2 brand, but Ben's lead. Alice is blocked from its contacts and can't create a duplicate |
| Thistle Extracts | CA's #3 brand, not in the CRM: a clean new prospect |
| ACC-1002 Copper Gardens | Orders down ~11%; sells edibles at retail but buys no edible packaging from us (whitespace) |
| ACC-1003 North Fork Provisions | Stopped ordering one product category three months ago |
| ACC-1004 Maplewood Farms | Alice's open prospect |

BDSA covers CA, MI, IL, MA, CO, NV: 50 brands each, Oct 2025 to Sep 2026.

**Demo script** (as Alice):
1. "Who are the top 10 brands in California this quarter? Which should I go after?"
2. "Get me the procurement contacts at Thistle Extracts."
3. "Create a lead for Thistle Extracts with the first contact."
4. "Remind me to call them next Tuesday."
5. "Get me contacts at Ember Labs." (withheld: Ben owns it)
6. "How is Copper Gardens doing? Any opportunities?"
7. "What's overdue?"
8. "Draft a short intro email to Thistle's purchasing lead."

## Making changes

| To... | Edit |
|---|---|
| Change how an agent behaves | `INSTRUCTIONS` (or `instructions()`) in that agent's file |
| Change a business rule | `aaa/services/` (`crm.py`, `followups.py`, `monitor.py`), then update the tests |
| Add a tool | Write a function in `aaa/services/`, wrap it with `@function_tool` in the specialist's file, and add it to that agent's `tools=[...]`. Read the rep from `ctx.context`; never add a rep parameter |
| Add a specialist | New file in `aaa/specialists/`, then add `agent.as_tool(...)` to `aaa/orchestrator.py` and describe it in AAA's instructions |
| Connect a real API | Replace the internals of `aaa/services/bdsa.py`, `zoominfo.py`, or `crm.py`. Keep the function signatures so the agents don't change |
| Change the mock data | Edit and rerun `scripts/generate_mock_data.py`; don't hand-edit `aaa/seed/*.json` |
| Pick a model | Set `AAA_MODEL` in `.env` (blank uses the SDK default) |

Run `pytest` after any change.

## Open questions for the business

- Which CRM, and what are the real ownership and territory rules? The prototype assigns leads by state.
- Should a teammate see contacts on another rep's record, or only status and owner (current behavior)?
- What can managers see and do?
- BDSA and ZoomInfo: API access, licensing, and data coverage.
- Reminder timing; Outlook calendar events or Teams messages only?
- Which accounts to monitor, how often, and is Instagram API access available?
- Data retention for conversations. OpenAI receives chat content to run the model, and the
  Agents SDK uploads traces by default.
