"""Structural checks on the agents that don't need an API key."""

from aaa.orchestrator import build_orchestrator
from aaa.specialists.contacts import contacts_agent
from aaa.specialists.crm_leads import crm_agent
from aaa.specialists.followups import followups_agent
from aaa.specialists.launch_monitor import launch_monitor_agent
from aaa.specialists.market_intel import market_intel_agent

SPECIALISTS = [market_intel_agent, contacts_agent, crm_agent, followups_agent, launch_monitor_agent]


def test_orchestrator_has_every_specialist():
    names = {t.name for t in build_orchestrator().tools}
    assert names == {"market_intel", "contacts", "crm", "followups", "launch_monitor"}


def test_no_tool_lets_the_model_choose_whose_data_it_reads():
    """Identity comes from the run context (the signed-in rep), never from tool arguments."""
    for agent in SPECIALISTS:
        for tool in agent.tools:
            params = set(tool.params_json_schema.get("properties", {}))
            assert not params & {"rep", "rep_id", "owner", "user", "user_id"}, (agent.name, tool.name)
