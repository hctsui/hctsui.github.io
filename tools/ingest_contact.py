#!/usr/bin/env python3
"""Create a privacy-safe Admin alert for a contact form submission.

The repository is public. Never persist sender names, addresses, subjects, or
message bodies here; Web3Forms delivers those privately by email.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from notification_store import upsert, validate_store

ROOT = Path(__file__).resolve().parents[1]
STORE_FILE = ROOT / "content" / "notifications.json"


def text(value: Any, limit: int) -> str:
    return re.sub(r"[\x00-\x1f]+", "", str(value or "")).strip()[:limit]


def build_notification(payload: dict[str, Any]) -> dict[str, Any]:
    received = text(payload.get("received_at"), 80) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event_id = text(payload.get("event_id"), 160)
    if not event_id:
        event_id = hashlib.sha256(received.encode("utf-8")).hexdigest()[:20]
    return {
        "key": f"contact:{event_id}",
        "type": "contact",
        "title": "收到新的網站聯絡訊息",
        "message": "完整內容已由 Web3Forms 私下寄到 Email；公開通知資料不保存訪客姓名、信箱或留言內容。",
        "created_at": received,
        "updated_at": received,
        "payload": {"event_id": event_id, "received_at": received},
        "actions": [
            {"id": "inbox", "label": "開啟 Email 收件匣"},
            {"id": "handled", "label": "標記為已處理"},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-file")
    parser.add_argument("--payload-json")
    args = parser.parse_args()
    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    elif args.payload_json:
        payload = json.loads(args.payload_json)
    else:
        raise ValueError("A contact event payload is required.")
    store = json.loads(STORE_FILE.read_text(encoding="utf-8")) if STORE_FILE.exists() else {}
    updated, changed = upsert(store, build_notification(payload))
    validate_store(updated)
    if changed or not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Contact alert added." if changed else "Contact alert already exists.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
