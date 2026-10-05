"""Who is talking to AAA.

In Teams, the rep's identity comes from their signed-in Microsoft account. Here
the CLI's --rep flag stands in for that. Every tool reads the rep from this
context and never from a model-supplied argument, so the model can't act as, or
read data on behalf of, another rep.
"""

from dataclasses import dataclass, field
from datetime import date

from . import store


@dataclass
class RepContext:
    rep_id: str
    name: str
    role: str  # "rep" or "manager"
    territory: list[str]
    today: date = field(default_factory=date.today)

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"

    def can_see(self, owner: str) -> bool:
        """Company rule: you see full detail on records you own; managers see everything."""
        return self.is_manager or owner == self.rep_id


def rep_names() -> dict[str, str]:
    return {r["rep_id"]: r["name"] for r in store.load("reps")}


def load_rep(rep_id: str, today: date | None = None) -> RepContext:
    for r in store.load("reps"):
        if r["rep_id"] == rep_id:
            return RepContext(rep_id=r["rep_id"], name=r["name"], role=r["role"],
                              territory=r["territory"], today=today or date.today())
    known = ", ".join(rep_names())
    raise ValueError(f"Unknown rep '{rep_id}'. Known reps: {known}")
