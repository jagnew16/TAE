# TAE Class Project: AAA Sales Assistant

AAA is an AI sales assistant for sales reps, delivered through Microsoft Teams. It covers prospect
research (BDSA), contact discovery (ZoomInfo), CRM duplicate checks and lead creation, follow-up
reminders, and monitoring customer websites and Instagram for product launches.

This repo has a working prototype of the agents, built on the
[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) with fictional mock data.

## Where things are

- [`AGENTS.md`](AGENTS.md): how to use and change the agents. AI assistants working in this repo should read this first.
- [`docs/business-requirements.md`](docs/business-requirements.md): what we're building.
- [`docs/agent-design.md`](docs/agent-design.md): how the agents are split up, what each one does,
  which rules are enforced in code, and the path to production.
- `index.html`: the rep dashboard (Christina's design), served by `python -m aaa serve` with live data.
- `aaa/`: the prototype.
  - `orchestrator.py`: AAA, the agent each rep chats with.
  - `specialists/`: Market Intel, Contacts, CRM & Leads, Follow-ups, Launch Monitor.
  - `services/`: the business rules and data access the tools call (testable without a model).
  - `jobs.py`: scheduled reminder and launch-monitoring jobs.
  - `web.py`: the web server and JSON API behind `index.html`.
  - `seed/`: mock BDSA, ZoomInfo, and CRM data (all fictional).
- `scripts/generate_mock_data.py`: regenerates the mock data.
- `tests/`: 45 tests, none of which need an API key.
- [`access-test/`](access-test/README.md): a check that each collaborator (and their AI tools) can
  read and write to this repo.

## Setup

Requires Python 3.10+ and an OpenAI API key.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then put your OPENAI_API_KEY in .env
```

## Try it

### Web dashboard

```bash
python -m aaa serve
```

Then open http://127.0.0.1:8000/?rep=alice. Every page shows live data from the same services the
agents use. Switch reps from the dropdown under the name (bottom left) to see the privacy rules: Ben
sees only his own work, and Dana (manager) sees everyone's. **Ask AAA**, and buttons like Review,
Prospect, and Prepare outreach, run the real agents and need `OPENAI_API_KEY` in `.env`. The
other pages work without it.

### Command line

Chat as one of the demo reps (`python -m aaa reps` lists them):

```bash
python -m aaa chat --rep alice
```

A demo script that hits every requirement (Alice covers CA and NV):

1. "Who are the top 10 brands in California this quarter? Which should I go after?"
   Customers and Ben's lead are flagged, not suggested.
2. "Get me the procurement contacts at Thistle Extracts."
3. "Create a lead for Thistle Extracts with the first contact."
4. "Remind me to call them next Tuesday."
5. "Get me contacts at Ember Labs." Withheld, because Ben owns it.
6. "How is Copper Gardens doing? Any opportunities?" Shows declining orders and a whitespace gap.
7. "What's overdue?"
8. "Draft a short intro email to Thistle's purchasing lead." General assistance.

Run the scheduled jobs, then reopen Alice's chat to see the Teams-style notifications:

```bash
python -m aaa reminders
python -m aaa monitor          # add --no-llm to skip model calls
python -m aaa chat --rep alice
```

Other commands: `python -m aaa reset` restores the demo data, and `pytest` runs the tests.
Set `AAA_MODEL` in `.env` to choose the model (default: the Agents SDK default).
