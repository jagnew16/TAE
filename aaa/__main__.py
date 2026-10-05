"""Command line for AAA.

  python -m aaa chat --rep alice                 # interactive private chat as Alice
  python -m aaa chat --rep alice "top 10 CA brands this quarter"   # one message
  python -m aaa reminders                        # send due/overdue follow-up reminders
  python -m aaa monitor [--no-llm]               # check watched sites/Instagram for launches
  python -m aaa serve [--port 8000]              # web dashboard at http://127.0.0.1:8000/?rep=alice
  python -m aaa reset                            # restore all data to the seed
  python -m aaa reps                             # list demo reps
"""

import argparse
import asyncio
import os
import sys

from . import config, store
from .context import load_rep


def require_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY isn't set. Copy .env.example to .env and add your key.")


def show_notifications(rep_id: str) -> None:
    from .services import notify
    for msg in notify.deliver(rep_id):
        print(f"\n[Teams notification · {msg['kind']}]\n{msg['text']}")
        if msg["link"]:
            print(msg["link"])


async def chat(rep_id: str, message: str | None) -> None:
    from .conversation import ask

    rep = load_rep(rep_id)

    async def turn(text: str) -> None:
        reply, used = await ask(rep, text)
        if used:
            print(f"  (asked: {', '.join(used)})")
        print(f"\nAAA: {reply}\n")

    if message:
        await turn(message)
        return
    print(f"AAA private chat for {rep.name}. Ctrl-D or 'exit' to leave.")
    show_notifications(rep.rep_id)
    while True:
        try:
            text = input(f"\n{rep.name.split()[0]}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text.lower() in {"exit", "quit"}:
            return
        if text:
            await turn(text)


def main() -> None:
    config.load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m aaa", description="AAA sales assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    p_chat = sub.add_parser("chat", help="chat with AAA as a rep")
    p_chat.add_argument("--rep", required=True, help="rep id (see `python -m aaa reps`)")
    p_chat.add_argument("message", nargs="?", help="send one message and exit")
    sub.add_parser("reminders", help="send due and overdue follow-up reminders")
    p_mon = sub.add_parser("monitor", help="check watched websites/Instagram for launches")
    p_mon.add_argument("--no-llm", action="store_true", help="keyword filter only, no API calls")
    p_serve = sub.add_parser("serve", help="run the web dashboard")
    p_serve.add_argument("--port", type=int, default=8000)
    sub.add_parser("reset", help="restore demo data to the seed")
    sub.add_parser("reps", help="list demo reps")
    args = parser.parse_args()

    if args.command == "chat":
        try:
            load_rep(args.rep)
        except ValueError as e:
            sys.exit(str(e))
        require_api_key()
        asyncio.run(chat(args.rep, args.message))
    elif args.command == "reminders":
        from .jobs import run_reminders
        sent = run_reminders()
        print(f"Sent {len(sent)} reminder message(s): " + ", ".join(m["rep"] for m in sent))
    elif args.command == "monitor":
        from .jobs import run_monitor
        if not args.no_llm:
            require_api_key()
        result = asyncio.run(run_monitor(use_llm=not args.no_llm))
        print(f"Checked {result['posts_checked']} new post(s); sent {len(result['alerts'])} launch alert(s).")
        for a in result["alerts"]:
            print(f"  → {a['rep']}: {a['text']}")
    elif args.command == "serve":
        import uvicorn
        print(f"AAA dashboard: http://127.0.0.1:{args.port}/?rep=alice")
        uvicorn.run("aaa.web:app", host="127.0.0.1", port=args.port)
    elif args.command == "reset":
        store.reset()
        print("Demo data reset to seed.")
    elif args.command == "reps":
        for r in store.load("reps"):
            print(f"{r['rep_id']:6} {r['name']:16} {r['role']:8} {', '.join(r['territory']) or 'all'}")


if __name__ == "__main__":
    main()
