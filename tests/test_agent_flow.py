"""Runs the real agent graph (AAA → specialist → tool) with a scripted model in place
of OpenAI, so the SDK plumbing is tested without an API key or network.

The scripted model calls one tool per agent and then echoes the tool's output, so
these tests check routing and identity, not the model's judgment.
"""

import asyncio
import json

import pytest
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from agents import Model, ModelResponse, Runner, Usage, set_tracing_disabled

from aaa import store
from aaa.orchestrator import build_orchestrator
from aaa.specialists import contacts, crm_leads, followups, launch_monitor, market_intel

set_tracing_disabled(True)


class ScriptedModel(Model):
    """Orchestrator: call `route` with a request. Specialist: call `action`. Then echo the result."""

    def __init__(self, route: tuple[str, str], action: tuple[str, dict]):
        self.route, self.action = route, action

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema,
                           handoffs, tracing, **kwargs):
        items = input if isinstance(input, list) else []
        outputs = [i for i in items if isinstance(i, dict) and i.get("type") == "function_call_output"]
        if outputs:
            return self._message(str(outputs[-1]["output"]))
        tool_names = {t.name for t in tools}
        if self.route[0] in tool_names:
            return self._call(self.route[0], {"input": self.route[1]})
        name, args = self.action
        assert name in tool_names, f"{name} not offered; got {tool_names}"
        return self._call(name, args)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError

    @staticmethod
    def _call(name, args):
        call = ResponseFunctionToolCall(type="function_call", call_id=f"call_{name}", name=name,
                                        arguments=json.dumps(args), id=f"fc_{name}", status="completed")
        return ModelResponse(output=[call], usage=Usage(), response_id=None)

    @staticmethod
    def _message(text):
        msg = ResponseOutputMessage(id="msg", type="message", role="assistant", status="completed",
                                    content=[ResponseOutputText(type="output_text", text=text, annotations=[])])
        return ModelResponse(output=[msg], usage=Usage(), response_id=None)


@pytest.fixture
def run(monkeypatch):
    def _run(rep, route, action):
        model = ScriptedModel(route, action)
        for mod, name in [(market_intel, "market_intel_agent"), (contacts, "contacts_agent"),
                          (crm_leads, "crm_agent"), (followups, "followups_agent"),
                          (launch_monitor, "launch_monitor_agent")]:
            monkeypatch.setattr(getattr(mod, name), "model", model)
        agent = build_orchestrator().clone(model=model)
        return asyncio.run(Runner.run(agent, "hi", context=rep)).final_output
    return _run


def test_rep_identity_reaches_the_specialists_tools(run, alice, ben):
    route = ("crm", "Is Ember Labs already in the CRM?")
    action = ("check_prospect", {"company": "Ember Labs", "website": None})
    as_alice = run(alice, route, action)
    as_ben = run(ben, route, action)
    assert "Another rep owns this record" in as_alice and "contact_email" not in as_alice
    assert "You already own this record" in as_ben and "contact_email" in as_ben


def test_followup_created_through_the_agent_chain(run, alice):
    run(alice, ("followups", "Remind me to send pricing to Maplewood on Oct 9"),
        ("create_followup", {"title": "Send pricing", "due": "2026-10-09", "record_id": "ACC-1004", "notes": ""}))
    task = store.load("tasks")[-1]
    assert task["rep"] == "alice" and task["record_id"] == "ACC-1004"


def test_market_intel_flags_through_the_chain(run, alice):
    out = run(alice, ("market_intel", "Top 10 CA brands last quarter"),
              ("top_brands", {"state": "CA", "top_n": 10, "period": "quarter"}))
    assert "'ok_to_prospect': False" in out and "Ben Okafor" in out
