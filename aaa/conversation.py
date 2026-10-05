"""One private conversation per rep, shared by the CLI and the web app."""

from agents import Runner, SQLiteSession

from . import store
from .context import RepContext
from .orchestrator import build_orchestrator

_agent = None
_sessions: dict[str, SQLiteSession] = {}


def session_for(rep_id: str) -> SQLiteSession:
    # One conversation store per rep: nobody else's history is ever loaded into this chat.
    if rep_id not in _sessions:
        folder = store.state_dir() / "sessions"
        folder.mkdir(exist_ok=True)
        _sessions[rep_id] = SQLiteSession(rep_id, folder / f"{rep_id}.db")
    return _sessions[rep_id]


async def ask(rep: RepContext, message: str) -> tuple[str, list[str]]:
    """AAA's reply, and which specialists it called."""
    global _agent
    _agent = _agent or build_orchestrator()
    result = await Runner.run(_agent, message, context=rep, session=session_for(rep.rep_id), max_turns=20)
    used = [getattr(i.raw_item, "name", None) for i in result.new_items if i.type == "tool_call_item"]
    return str(result.final_output), list(dict.fromkeys(n for n in used if n))
