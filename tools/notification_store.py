#!/usr/bin/env python3
"""Shared persistent notification model for the static Admin notification center."""
from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1
RETENTION_DAYS = 60
TYPES = {"publication_status", "broken_link", "contact", "system"}
STATUSES = {"open", "resolved"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _id_from_key(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.casefold()).strip("-")[:72] or "notification"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{digest}"


def empty_store() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "retention_days": RETENTION_DAYS,
        "notifications": [],
    }


def normalize_notification(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kind = _text(value.get("type"), 80)
    if kind not in TYPES:
        return None
    key = _text(value.get("key"), 500)
    if not key:
        return None
    created_at = _text(value.get("created_at"), 80) or utc_now()
    updated_at = _text(value.get("updated_at"), 80) or created_at
    status = _text(value.get("status"), 40)
    if status not in STATUSES:
        status = "open"
    payload = copy.deepcopy(value.get("payload")) if isinstance(value.get("payload"), dict) else {}
    actions = []
    for action in value.get("actions", []) if isinstance(value.get("actions"), list) else []:
        if not isinstance(action, dict):
            continue
        action_id = _text(action.get("id"), 80)
        label = _text(action.get("label"), 120)
        if action_id and label:
            actions.append({"id": action_id, "label": label})
    return {
        "id": _text(value.get("id"), 120) or _id_from_key(key),
        "key": key,
        "type": kind,
        "title": _text(value.get("title"), 500),
        "message": _text(value.get("message"), 4000),
        "created_at": created_at,
        "updated_at": updated_at,
        "starred": bool(value.get("starred", False)),
        "read": bool(value.get("read", False)),
        "status": status,
        "source_url": _text(value.get("source_url"), 2000),
        "payload": payload,
        "actions": actions,
    }


def normalized_store(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    try:
        retention = max(1, min(3650, int(source.get("retention_days", RETENTION_DAYS))))
    except (TypeError, ValueError):
        retention = RETENTION_DAYS
    by_key: dict[str, dict[str, Any]] = {}
    for raw in source.get("notifications", []) if isinstance(source.get("notifications"), list) else []:
        item = normalize_notification(raw)
        if item:
            by_key[item["key"]] = item
    rows = sorted(
        by_key.values(),
        key=lambda item: (item["starred"], item["updated_at"], item["created_at"], item["id"]),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "retention_days": retention,
        "notifications": rows,
    }


def validate_store(value: Any) -> None:
    store = normalized_store(value)
    seen: set[str] = set()
    for item in store["notifications"]:
        if item["key"] in seen:
            raise ValueError(f"Duplicate notification key: {item['key']}")
        seen.add(item["key"])
        if not item["title"]:
            raise ValueError(f"Notification {item['key']} has no title.")


def upsert(store: dict[str, Any], candidate: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    current = normalized_store(store)
    fresh = normalize_notification(candidate)
    if not fresh:
        raise ValueError("Invalid notification candidate.")
    existing = next((row for row in current["notifications"] if row["key"] == fresh["key"]), None)
    if existing:
        # Preserve user-managed state across automated refreshes.
        fresh["id"] = existing["id"]
        fresh["created_at"] = existing["created_at"]
        fresh["starred"] = existing["starred"]
        fresh["read"] = existing["read"]
        # A resolved notification stays resolved when an automated checker sees
        # the same condition again. A genuinely new condition must use a new key.
        fresh["status"] = existing["status"]
    before = copy.deepcopy(current)
    rows = [row for row in current["notifications"] if row["key"] != fresh["key"]]
    rows.append(fresh)
    current["notifications"] = rows
    current = normalized_store(current)
    return current, current != before


def resolve_key(store: dict[str, Any], key: str, *, remove: bool = False) -> tuple[dict[str, Any], bool]:
    current = normalized_store(store)
    before = copy.deepcopy(current)
    if remove:
        current["notifications"] = [row for row in current["notifications"] if row["key"] != key]
    else:
        for row in current["notifications"]:
            if row["key"] == key:
                row["status"] = "resolved"
                row["read"] = True
                row["updated_at"] = utc_now()
    current = normalized_store(current)
    return current, current != before
