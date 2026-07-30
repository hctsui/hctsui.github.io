#!/usr/bin/env python3
"""Validate content schema, ordering references, URLs, and generated pages."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
errors: list[str] = []
ids: list[str] = []

SECTION_TYPES = {
    "activities": {"conference", "talk", "visit"},
    "honors": {"honor"},
    "publications": {"publication"},
    "teaching": {"teaching"},
}


def has_any_language(value: object) -> bool:
    if isinstance(value, dict):
        return bool(str(value.get("en") or "").strip() or str(value.get("zh") or "").strip())
    return bool(str(value or "").strip())


def check_url(value: object, context: str) -> None:
    text = str(value or "").strip()
    if not text:
        return
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https", "mailto"}:
        errors.append(f"{context}: URL must use http, https, or mailto")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        errors.append(f"{context}: URL is missing a host")


records_by_type: dict[str, list[dict]] = {kind: [] for kinds in SECTION_TYPES.values() for kind in kinds}
record_ids: dict[str, dict[str, dict]] = {kind: {} for kind in records_by_type}

for section, allowed_types in SECTION_TYPES.items():
    rows = data.get(section)
    if not isinstance(rows, list):
        errors.append(f"{section} must be a list")
        continue

    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            errors.append(f"{section}[{index}] must be an object")
            continue

        eid = str(item.get("id") or "").strip()
        kind = item.get("type")
        if not eid:
            errors.append(f"{section}[{index}]: missing id")
        else:
            ids.append(eid)
        if kind not in allowed_types:
            errors.append(f"{eid or section}: invalid type '{kind}' for {section}")
            continue

        records_by_type[kind].append(item)
        if eid:
            record_ids[kind][eid] = item

        field = "course" if kind == "teaching" else "title"
        if not has_any_language(item.get(field, {})):
            errors.append(f"{eid}: {field} must contain at least one language")

        if kind in {"conference", "talk", "visit"}:
            try:
                start = date.fromisoformat(item["start_date"])
                end = date.fromisoformat(item.get("end_date") or item["start_date"])
                if end < start:
                    errors.append(f"{eid}: end date before start date")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{eid}: invalid activity date")
            if "show_upcoming" in item and not isinstance(item["show_upcoming"], bool):
                errors.append(f"{eid}: show_upcoming must be boolean")

        if kind == "publication":
            try:
                published = date.fromisoformat(item["date"])
                if int(item.get("year", published.year)) != published.year:
                    errors.append(f"{eid}: year does not match publication date")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{eid}: invalid publication date or year")

        if kind == "honor":
            try:
                int(item["year"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"{eid}: invalid honor year")

        for key, value in item.items():
            if key == "url" or key.endswith("_url"):
                check_url(value, f"{eid}.{key}")
        for link_index, link in enumerate(item.get("links", []), start=1):
            if not isinstance(link, dict):
                errors.append(f"{eid}.links[{link_index}] must be an object")
            else:
                check_url(link.get("url"), f"{eid}.links[{link_index}]")

if len(ids) != len(set(ids)):
    errors.append("Entry IDs are not unique")

settings = data.get("settings", {})
if not isinstance(settings, dict):
    errors.append("settings must be an object")
    settings = {}

entry_order = settings.get("entry_order", {})
if not isinstance(entry_order, dict):
    errors.append("settings.entry_order must be an object")
else:
    for kind, order in entry_order.items():
        if kind not in records_by_type:
            errors.append(f"settings.entry_order has unsupported type: {kind}")
            continue
        if not isinstance(order, list):
            errors.append(f"settings.entry_order.{kind} must be a list")
            continue
        if len(order) != len(set(order)):
            errors.append(f"settings.entry_order.{kind} contains duplicate IDs")
        missing = [eid for eid in order if eid not in record_ids[kind]]
        if missing:
            errors.append(f"settings.entry_order.{kind} refers to missing IDs: {', '.join(missing[:5])}")

content_groups = settings.get("content_groups", {})
if not isinstance(content_groups, dict):
    errors.append("settings.content_groups must be an object")
    content_groups = {}
for kind in ("publication", "teaching"):
    groups = content_groups.get(kind, [])
    if not isinstance(groups, list):
        errors.append(f"settings.content_groups.{kind} must be a list")
        continue
    group_ids = [str(group.get("id") or "") for group in groups if isinstance(group, dict)]
    if len(group_ids) != len(set(group_ids)):
        errors.append(f"settings.content_groups.{kind} contains duplicate group IDs")
    known = set(group_ids)
    for item in records_by_type[kind]:
        gid = str(item.get("group_id") or "")
        if not gid or gid not in known:
            errors.append(f"{item.get('id')}: unknown or missing {kind} group_id '{gid}'")

markers = {
    "index.html": ["HOME_PUBLICATIONS", "UPCOMING"],
    "zh/index.html": ["HOME_PUBLICATIONS", "UPCOMING"],
    "activities.html": ["VISITS", "TALKS", "CONFERENCES"],
    "zh/activities.html": ["VISITS", "TALKS", "CONFERENCES"],
    "cv.html": ["HONORS"],
    "zh/cv.html": ["HONORS"],
    "publications.html": ["PUBLICATIONS"],
    "zh/publications.html": ["PUBLICATIONS"],
    "teaching.html": ["TEACHING"],
    "zh/teaching.html": ["TEACHING"],
}
for rel, names in markers.items():
    text = (ROOT / rel).read_text(encoding="utf-8")
    if text.lower().count("<!doctype html>") != 1:
        errors.append(f"{rel}: must contain exactly one doctype")
    for name in names:
        if text.count(f"<!-- CMS:{name}:START -->") != 1 or text.count(f"<!-- CMS:{name}:END -->") != 1:
            errors.append(f"{rel}: invalid marker {name}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Validated {len(ids)} entries and {len(markers)} pages.")
