#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "content" / "site.json"
HISTORY = ROOT / "content" / "change-history.json"
RETENTION_DAYS = 7

SECTIONS = {
    "conference": "activities",
    "talk": "activities",
    "visit": "activities",
    "honor": "honors",
    "publication": "publications",
    "teaching": "teaching",
}


def parse_body(body: str) -> dict[str, Any]:
    match = re.search(
        r"### Batch payload / 批次資料\s+(.+)",
        body,
        re.S,
    )
    raw = (match.group(1) if match else body).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return json.loads((fence.group(1) if fence else raw).strip())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def clean_html(value: Any) -> str:
    return html.escape(str(value or "").strip(), quote=False)


def comparable(item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compare content while ignoring display-order bookkeeping."""
    if item is None:
        return None
    result = copy.deepcopy(item)
    result.pop("order", None)
    return result


def same_object(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    return comparable(left) == comparable(right)


def normalize(item: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(item)
    kind = result["type"]

    for key in (
        "title",
        "description",
        "organization",
        "authors",
        "venue",
    ):
        if isinstance(result.get(key), dict):
            result[f"{key}_html"] = {
                lang: clean_html(text)
                for lang, text in result[key].items()
            }

    if kind == "publication":
        result["year"] = int(
            str(result.get("date", ""))[:4]
            or result.get("year")
            or 0
        )

    return result


def load_history() -> dict[str, Any]:
    if not HISTORY.exists():
        return {
            "schema_version": 1,
            "retention_days": RETENTION_DAYS,
            "operations": [],
        }

    data = json.loads(HISTORY.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported change-history schema.")
    if not isinstance(data.get("operations"), list):
        raise ValueError("change-history operations must be an array.")
    data["retention_days"] = RETENTION_DAYS
    return data


def prune_history(history: dict[str, Any], now: datetime) -> None:
    kept = []
    for entry in history.get("operations", []):
        expires_at = entry.get("expires_at")
        if not expires_at:
            continue
        try:
            if parse_time(expires_at) > now:
                kept.append(entry)
        except ValueError:
            continue
    history["operations"] = kept


def find_entry(
    data: dict[str, Any],
    kind: str,
    entry_id: str,
) -> tuple[list[dict[str, Any]], int | None]:
    section = SECTIONS[kind]
    items = data.setdefault(section, [])
    index = next(
        (i for i, item in enumerate(items) if item.get("id") == entry_id),
        None,
    )
    return items, index


def title_snapshot(item: dict[str, Any] | None) -> dict[str, str]:
    if not item:
        return {"en": "", "zh": ""}

    for key in ("title", "course"):
        pair = item.get(key)
        if isinstance(pair, dict):
            return {
                "en": str(pair.get("en") or ""),
                "zh": str(pair.get("zh") or ""),
            }

    return {
        "en": str(item.get("id") or ""),
        "zh": "",
    }


def make_history_id(issue_number: int, op_index: int) -> str:
    return f"issue-{issue_number}-op-{op_index}"


def ensure_replay_matches(
    existing: dict[str, Any],
    request_digest: str,
) -> None:
    if existing.get("request_digest") != request_digest:
        raise ValueError(
            f"History ID {existing.get('history_id')} already exists "
            "with different batch content."
        )


def append_history(
    history: dict[str, Any],
    *,
    history_id: str,
    issue_number: int,
    applied_at: datetime,
    request_digest: str,
    request_action: str,
    action: str,
    kind: str,
    entry_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    index_before: int | None,
    index_after: int | None,
    undo_of: str | None = None,
) -> dict[str, Any]:
    entry = {
        "history_id": history_id,
        "batch_issue": issue_number,
        "applied_at": iso_z(applied_at),
        "expires_at": iso_z(
            applied_at + timedelta(days=RETENTION_DAYS)
        ),
        "request_action": request_action,
        "action": action,
        "type": kind,
        "entry_id": entry_id,
        "label": title_snapshot(after or before),
        "before": before,
        "after": after,
        "index_before": index_before,
        "index_after": index_after,
        "undo_of": undo_of,
        "reverted_by": None,
        "request_digest": request_digest,
    }
    history["operations"].append(entry)
    return entry


def apply_normal_operation(
    data: dict[str, Any],
    history: dict[str, Any],
    op: dict[str, Any],
    *,
    history_id: str,
    issue_number: int,
    applied_at: datetime,
    request_digest: str,
) -> tuple[str, str]:
    action = op["op"]
    kind = op["type"]
    entry_id = op.get("id") or op.get("after", {}).get("id")
    if not entry_id:
        raise ValueError("Operation is missing an entry ID.")

    items, index = find_entry(data, kind, entry_id)

    if action == "delete":
        if index is None:
            raise ValueError(f"Delete target not found: {entry_id}")
        current = copy.deepcopy(items[index])
        expected = op.get("before")
        if expected and not same_object(current, expected):
            raise ValueError(
                f"Conflict: {entry_id} changed after Admin loaded."
            )
        items.pop(index)
        append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="delete",
            action="delete",
            kind=kind,
            entry_id=entry_id,
            before=current,
            after=None,
            index_before=index,
            index_after=None,
        )
        return action, entry_id

    if action == "update":
        if index is None:
            raise ValueError(f"Update target not found: {entry_id}")
        current = copy.deepcopy(items[index])
        expected = op.get("before")
        if expected and not same_object(current, expected):
            raise ValueError(
                f"Conflict: {entry_id} changed after Admin loaded."
            )
        after = normalize(op["after"])
        after["id"] = entry_id
        items[index] = after
        append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="update",
            action="update",
            kind=kind,
            entry_id=entry_id,
            before=current,
            after=copy.deepcopy(after),
            index_before=index,
            index_after=index,
        )
        return action, entry_id

    if action == "add":
        after = normalize(op["after"])
        entry_id = after["id"]

        all_ids = {
            item.get("id")
            for section in set(SECTIONS.values())
            for item in data.get(section, [])
        }
        if entry_id in all_ids:
            base = entry_id
            suffix = 2
            while f"{base}-{suffix}" in all_ids:
                suffix += 1
            entry_id = f"{base}-{suffix}"
            after["id"] = entry_id

        items, _ = find_entry(data, kind, entry_id)
        index_after = len(items)
        items.append(after)
        append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="add",
            action="add",
            kind=kind,
            entry_id=entry_id,
            before=None,
            after=copy.deepcopy(after),
            index_before=None,
            index_after=index_after,
        )
        return action, entry_id

    raise ValueError(f"Unknown operation: {action}")


def apply_undo_operation(
    data: dict[str, Any],
    history: dict[str, Any],
    op: dict[str, Any],
    *,
    history_id: str,
    issue_number: int,
    applied_at: datetime,
    request_digest: str,
) -> tuple[str, str]:
    target_id = str(op.get("history_id") or "").strip()
    if not target_id:
        raise ValueError("Undo operation is missing history_id.")

    target = next(
        (
            entry
            for entry in history.get("operations", [])
            if entry.get("history_id") == target_id
        ),
        None,
    )
    if target is None:
        raise ValueError(
            f"Undo target is unavailable or older than seven days: "
            f"{target_id}"
        )
    if target.get("reverted_by"):
        raise ValueError(
            f"Operation {target_id} was already undone by "
            f"{target['reverted_by']}."
        )
    if parse_time(target["expires_at"]) <= applied_at:
        raise ValueError(f"Undo period expired for {target_id}.")

    kind = target["type"]
    entry_id = target["entry_id"]
    items, index = find_entry(data, kind, entry_id)
    original_action = target["action"]

    if original_action == "add":
        if index is None:
            raise ValueError(
                f"Cannot undo add: {entry_id} no longer exists."
            )
        current = copy.deepcopy(items[index])
        if not same_object(current, target.get("after")):
            raise ValueError(
                f"Cannot undo add: {entry_id} was modified later."
            )
        items.pop(index)
        new_entry = append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="undo",
            action="delete",
            kind=kind,
            entry_id=entry_id,
            before=current,
            after=None,
            index_before=index,
            index_after=None,
            undo_of=target_id,
        )

    elif original_action == "update":
        if index is None:
            raise ValueError(
                f"Cannot undo update: {entry_id} no longer exists."
            )
        current = copy.deepcopy(items[index])
        if not same_object(current, target.get("after")):
            raise ValueError(
                f"Cannot undo update: {entry_id} was modified later."
            )
        restored = copy.deepcopy(target.get("before"))
        if not restored:
            raise ValueError(
                f"Cannot undo update: missing previous snapshot for {entry_id}."
            )
        items[index] = restored
        new_entry = append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="undo",
            action="update",
            kind=kind,
            entry_id=entry_id,
            before=current,
            after=copy.deepcopy(restored),
            index_before=index,
            index_after=index,
            undo_of=target_id,
        )

    elif original_action == "delete":
        if index is not None:
            raise ValueError(
                f"Cannot undo delete: ID {entry_id} is already in use."
            )
        restored = copy.deepcopy(target.get("before"))
        if not restored:
            raise ValueError(
                f"Cannot undo delete: missing deleted snapshot for {entry_id}."
            )
        insert_at = target.get("index_before")
        if not isinstance(insert_at, int):
            insert_at = len(items)
        insert_at = min(max(insert_at, 0), len(items))
        items.insert(insert_at, restored)
        new_entry = append_history(
            history,
            history_id=history_id,
            issue_number=issue_number,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="undo",
            action="add",
            kind=kind,
            entry_id=entry_id,
            before=None,
            after=copy.deepcopy(restored),
            index_before=None,
            index_after=insert_at,
            undo_of=target_id,
        )

    else:
        raise ValueError(
            f"Unsupported history action for undo: {original_action}"
        )

    target["reverted_by"] = new_entry["history_id"]
    return "undo", entry_id


def normalize_groups_and_order(data: dict[str, Any]) -> None:
    for section in ("honors", "publications", "teaching"):
        for index, item in enumerate(data.get(section, [])):
            item["order"] = index

    groups = (
        data.setdefault("settings", {})
        .setdefault("content_groups", {})
    )

    for kind, section in (
        ("publication", "publications"),
        ("teaching", "teaching"),
    ):
        used = {
            item.get("group_id")
            for item in data.get(section, [])
            if item.get("group_id")
        }
        groups[kind] = [
            group
            for group in groups.get(kind, [])
            if group.get("preset") or group.get("id") in used
        ]
        known = {group.get("id") for group in groups[kind]}

        for item in data.get(section, []):
            group_id = item.get("group_id")
            if not group_id or group_id in known:
                continue

            label = item.get("group_label")
            if not label:
                label = (
                    item.get("institution")
                    if kind == "teaching"
                    else {"en": group_id, "zh": ""}
                )

            groups[kind].append(
                {
                    "id": group_id,
                    "label": label,
                    "order": len(groups[kind]),
                }
            )
            known.add(group_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event")
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args()

    event = json.load(open(args.event, encoding="utf-8"))
    issue = event["issue"]
    issue_number = int(issue["number"])
    payload = parse_body(issue["body"])
    operations = payload.get("operations", [])

    if payload.get("schema_version") not in (1, 2):
        raise ValueError("Invalid batch payload schema.")
    if not isinstance(operations, list):
        raise ValueError("Batch operations must be an array.")

    data = json.load(open(DATA, encoding="utf-8"))
    history = load_history()
    applied_at = utc_now()
    prune_history(history, applied_at)

    existing_history = {
        entry["history_id"]: entry
        for entry in history.get("operations", [])
    }

    counts = {
        "add": 0,
        "update": 0,
        "delete": 0,
        "undo": 0,
        "replayed": 0,
    }
    entry_ids: list[str] = []

    for op_index, operation in enumerate(operations, start=1):
        history_id = make_history_id(issue_number, op_index)
        request_digest = digest(operation)

        if history_id in existing_history:
            ensure_replay_matches(
                existing_history[history_id],
                request_digest,
            )
            counts["replayed"] += 1
            continue

        if operation.get("op") == "undo":
            action, entry_id = apply_undo_operation(
                data,
                history,
                operation,
                history_id=history_id,
                issue_number=issue_number,
                applied_at=applied_at,
                request_digest=request_digest,
            )
        else:
            action, entry_id = apply_normal_operation(
                data,
                history,
                operation,
                history_id=history_id,
                issue_number=issue_number,
                applied_at=applied_at,
                request_digest=request_digest,
            )

        counts[action] += 1
        entry_ids.append(entry_id)
        existing_history[history_id] = history["operations"][-1]

    normalize_groups_and_order(data)

    DATA.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    HISTORY.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = (
        f"批次完成：新增 {counts['add']}、修改 {counts['update']}、"
        f"刪除 {counts['delete']}、復原 {counts['undo']}"
    )
    if counts["replayed"]:
        summary += f"；略過已套用操作 {counts['replayed']}"

    result = {
        "action": summary,
        "entry_id": ", ".join(entry_ids[:8])
        + ("…" if len(entry_ids) > 8 else ""),
        "notes": [
            "每筆操作已寫入七日暫存垃圾桶，可在 Admin 單筆復原。"
        ],
        "warnings": [],
    }
    Path(args.result_file).write_text(
        json.dumps(result, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
