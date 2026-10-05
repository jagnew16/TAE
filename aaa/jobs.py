"""Scheduled jobs. In production these run on a timer (e.g. reminders every morning,
monitoring every few hours) and post to Teams. Here they write to the outbox."""

from datetime import date

from agents import Runner

from .services import crm, followups, monitor, notify
from .specialists.launch_monitor import LaunchAssessment, launch_classifier


def run_reminders(today: date | None = None) -> list[dict]:
    return followups.send_due_reminders(today)


async def _is_launch(post: dict, entry: dict, use_llm: bool) -> str | None:
    """A one-sentence summary if the post announces a launch, else None."""
    if not monitor.looks_like_launch(post["text"]):
        return None
    if not use_llm:
        return post["text"]
    result = await Runner.run(
        launch_classifier,
        f"Company: {entry['company']}\nSource: {post['source']} ({post['account']})\n\n{post['text']}")
    assessment: LaunchAssessment = result.final_output
    return assessment.summary if assessment.is_product_launch else None


async def run_monitor(use_llm: bool = True) -> dict:
    posts = monitor.new_posts()
    # Brands often announce the same launch on Instagram and their site: one alert per company.
    by_company: dict[str, tuple[dict, list[tuple[dict, str]]]] = {}
    for post, entry in posts:
        summary = await _is_launch(post, entry, use_llm)
        if summary:
            by_company.setdefault(entry["id"], (entry, []))[1].append((post, summary))

    alerts = []
    for entry, launches in by_company.values():
        owner = crm.owner_of(entry["record_id"])
        if not owner:
            continue
        text = f"New launch from {entry['company']}: {launches[0][1]}"
        if len(launches) > 1:
            text += "\nAlso seen at: " + ", ".join(p["url"] for p, _ in launches[1:])
        alerts.append(notify.send(owner, "launch", text, link=launches[0][0]["url"]))
    monitor.mark_seen([post["id"] for post, _ in posts])
    return {"posts_checked": len(posts), "alerts": alerts}
