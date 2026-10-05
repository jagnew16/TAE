"""Stand-in for Microsoft Teams proactive messages.

Notifications go to an outbox (state/outbox.json). The chat CLI shows a rep their
undelivered messages when they open AAA, the way Teams would show them in the
rep's private chat. With Teams, `send()` would post a proactive message
to that user's 1:1 conversation instead.
"""

from datetime import datetime

from .. import store


def send(rep_id: str, kind: str, text: str, link: str | None = None) -> dict:
    outbox = store.load("outbox")
    msg = {"id": store.next_id("MSG", outbox), "rep": rep_id, "kind": kind, "text": text,
           "link": link, "sent_at": datetime.now().isoformat(timespec="seconds"), "delivered": False}
    outbox.append(msg)
    store.save("outbox", outbox)
    return msg


def deliver(rep_id: str) -> list[dict]:
    """Undelivered messages for this rep only, marked delivered."""
    outbox = store.load("outbox")
    mine = [m for m in outbox if m["rep"] == rep_id and not m["delivered"]]
    for m in mine:
        m["delivered"] = True
    store.save("outbox", outbox)
    return mine
