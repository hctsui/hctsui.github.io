#!/usr/bin/env python3
"""Remove old unstarred notifications while preserving starred items."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notification_store import normalized_store, validate_store

ROOT = Path(__file__).resolve().parents[1]
STORE_FILE = ROOT / "content" / "notifications.json"
ARXIV_FILE = ROOT / "content" / "arxiv-suggestions.json"


def parse_time(value: str) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        result = datetime.fromisoformat(text)
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cleanup_store(store: dict, now: datetime | None = None) -> tuple[dict, int]:
    current = normalized_store(store)
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(days=current["retention_days"])
    kept = []
    removed = 0
    for item in current["notifications"]:
        stamp = parse_time(item.get("updated_at")) or parse_time(item.get("created_at"))
        if not item.get("starred") and stamp and stamp < cutoff:
            removed += 1
        else:
            kept.append(item)
    current["notifications"] = kept
    current = normalized_store(current)
    validate_store(current)
    return current, removed


def cleanup_arxiv(value: dict, now: datetime | None = None, retention_days: int = 60) -> tuple[dict, int]:
    source = value if isinstance(value, dict) else {}
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(days=retention_days)
    kept = []
    removed = 0
    for item in source.get("suggestions", []) if isinstance(source.get("suggestions"), list) else []:
        stamp = parse_time(item.get("discovered_at") or item.get("updated") or item.get("published"))
        if not bool(item.get("starred")) and stamp and stamp < cutoff:
            removed += 1
        else:
            kept.append(item)
    result = dict(source)
    result["suggestions"] = kept
    return result, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", help="ISO timestamp used by tests.")
    args = parser.parse_args()
    moment = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    store = json.loads(STORE_FILE.read_text(encoding="utf-8")) if STORE_FILE.exists() else {}
    cleaned, count = cleanup_store(store, moment)
    if cleaned != normalized_store(store) or not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    arxiv_count = 0
    if ARXIV_FILE.exists():
        raw = json.loads(ARXIV_FILE.read_text(encoding="utf-8"))
        updated, arxiv_count = cleanup_arxiv(raw, moment, cleaned["retention_days"])
        if updated != raw:
            ARXIV_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Removed {count} general and {arxiv_count} arXiv notification(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
