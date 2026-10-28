#!/usr/bin/env python3
"""Materialize the Admin daily time and IANA timezone in GitHub Actions cron.

GitHub cannot evaluate expressions in on.schedule.  Run this after applying
site-settings Batch changes, before staging the commit.  Updating a workflow
from Actions requires an appropriately privileged PAT/GitHub App token.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "content/site.json"
WORKFLOW = ROOT / ".github/workflows/daily-upcoming.yml"
START = "  # AUTO_DAILY_SCHEDULE_BEGIN -- managed from Admin > 自動更新"
END = "  # AUTO_DAILY_SCHEDULE_END"


def schedule(data: dict) -> dict:
    settings = data.get("settings") or {}
    legacy = settings.get("timezone") or "Asia/Tokyo"
    value = settings.get("auto_update") or {"enabled": True, "time": "00:15", "timezone": legacy}
    if not isinstance(value, dict) or type(value.get("enabled", True)) is not bool:
        raise ValueError("Invalid auto_update.enabled setting")
    enabled = value.get("enabled", True)
    time = str(value.get("time", "00:15"))
    zone = str(value.get("timezone", legacy))
    if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", time):
        raise ValueError("Invalid auto_update.time: expected HH:MM")
    try:
        ZoneInfo(zone)
    except (ValueError, ZoneInfoNotFoundError, KeyError) as error:
        raise ValueError(f"Invalid IANA timezone {zone!r}") from error
    return {"enabled": enabled, "time": time, "timezone": zone}


def render(config: dict) -> str:
    if not config["enabled"]:
        return f"{START}\n  # Daily run disabled in the Admin.\n{END}"
    hour, minute = (int(x) for x in config["time"].split(":"))
    return (
        f"{START}\n"
        f"  schedule:\n"
        f'    - cron: "{minute} {hour} * * *"\n'
        f'      timezone: "{config["timezone"]}"\n'
        f"{END}"
    )


def sync(site: Path = SOURCE, workflow: Path = WORKFLOW) -> bool:
    config = schedule(json.loads(site.read_text(encoding="utf-8")))
    old = workflow.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    new, count = pattern.subn(lambda _: render(config), old)
    if count != 1:
        raise RuntimeError("Daily workflow managed schedule markers are missing or duplicated")
    if old == new:
        print(f"Daily schedule already up to date: {config}")
        return False
    workflow.write_text(new, encoding="utf-8")
    print(f"Updated GitHub native daily schedule: {config}")
    return True


if __name__ == "__main__":
    sync()
