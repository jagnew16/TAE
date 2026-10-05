"""Local JSON storage standing in for the real systems (CRM, task store, Teams outbox).

On first use each collection is copied from aaa/seed/ into the state directory,
and every write goes to the state copy, so the seed files never change.
`reset()` puts everything back to the seed.

Seed fields named `<x>_in_days` become a date `<x>` relative to today when the
state is created, which keeps follow-up tasks overdue/upcoming no matter when
the demo runs.
"""

import json
import os
import shutil
from datetime import date, timedelta
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent / "seed"


def state_dir() -> Path:
    path = Path(os.environ.get("AAA_STATE_DIR", Path.cwd() / "state"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_relative_dates(value, today: date):
    if isinstance(value, list):
        return [_resolve_relative_dates(v, today) for v in value]
    if isinstance(value, dict):
        out = {}
        for key, v in value.items():
            if key.endswith("_in_days") and isinstance(v, int):
                out[key[: -len("_in_days")]] = (today + timedelta(days=v)).isoformat()
            else:
                out[key] = _resolve_relative_dates(v, today)
        return out
    return value


def load(name: str):
    path = state_dir() / f"{name}.json"
    if not path.exists():
        seed = SEED_DIR / f"{name}.json"
        data = json.loads(seed.read_text()) if seed.exists() else []
        save(name, _resolve_relative_dates(data, date.today()))
    return json.loads(path.read_text())


def save(name: str, data) -> None:
    path = state_dir() / f"{name}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n")
    tmp.replace(path)


def next_id(prefix: str, records: list) -> str:
    numbers = [int(r["id"].split("-")[1]) for r in records if r.get("id", "").startswith(prefix + "-")]
    return f"{prefix}-{max(numbers, default=0) + 1}"


def reset() -> None:
    shutil.rmtree(state_dir(), ignore_errors=True)
