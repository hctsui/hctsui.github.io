#!/usr/bin/env python3
"""Validate schema 3 content, managed categories, URLs, and generated pages."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from category_config import all_items, categories_for_page, migrate_category_data, validate_category_data
from homepage_config import validate_homepage_config

ROOT = Path(__file__).resolve().parents[1]
data = migrate_category_data(json.loads((ROOT / "content/site.json").read_text(encoding="utf-8")))
errors: list[str] = []

SECTION_TYPES = {
    "activities": {"conference", "talk", "visit", "organization"},
    "honors": {"honor"},
    "publications": {"publication"},
    "teaching": {"teaching"},
    "profile_items": {"interest", "education", "generic", "contact", "personal"},
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
        kind = str(item.get("type") or "")
        if not eid:
            errors.append(f"{section}[{index}]: missing id")
        if kind not in allowed_types:
            errors.append(f"{eid or section}: invalid type '{kind}' for {section}")
            continue
        field = "course" if kind == "teaching" else "title"
        if not has_any_language(item.get(field, {})):
            errors.append(f"{eid}: {field} must contain at least one language")
        if kind in {"conference", "talk", "visit", "organization"}:
            try:
                start = date.fromisoformat(item["start_date"])
                end = date.fromisoformat(item.get("end_date") or item["start_date"])
                if end < start:
                    errors.append(f"{eid}: end date before start date")
            except (KeyError, TypeError, ValueError):
                errors.append(f"{eid}: invalid activity date")
            if kind == "organization":
                if not has_any_language(item.get("organization_kind", {})):
                    errors.append(f"{eid}: organization_kind must contain at least one language")
                if not has_any_language(item.get("role", {})):
                    errors.append(f"{eid}: role must contain at least one language")
            if "show_in_organization" in item:
                errors.append(f"{eid}: conference and organization must be independent records; remove show_in_organization")
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

try:
    validate_category_data(data)
except ValueError as exc:
    errors.append(str(exc))
try:
    validate_homepage_config(data, data.get("settings", {}).get("homepage"))
except ValueError as exc:
    errors.append(str(exc))

ids = [str(item.get("id") or "") for item in all_items(data)]
if len(ids) != len(set(ids)):
    errors.append("Entry IDs are not unique")

page_files = {
    "home": ("index.html", "zh/index.html"),
    "cv": ("cv.html", "zh/cv.html"),
    "publications": ("publications.html", "zh/publications.html"),
    "activities": ("activities.html", "zh/activities.html"),
    "teaching": ("teaching.html", "zh/teaching.html"),
}
for page_id, files in page_files.items():
    category_ids = [c["id"] for c in categories_for_page(data, page_id) if c.get("show_on_web", True)]
    for rel in files:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if text.lower().count("<!doctype html>") != 1:
            errors.append(f"{rel}: must contain exactly one doctype")
        if text.count('<main id="main">') != 1:
            errors.append(f"{rel}: must contain exactly one main element")
        for category_id in category_ids:
            count = text.count(f'data-category-id="{category_id}"')
            # Empty categories are intentionally hidden.
            has_items = any(item.get("category_id") == category_id for item in all_items(data))
            if has_items and count != 1:
                errors.append(f"{rel}: category {category_id} should appear exactly once")

home_categories = categories_for_page(data, "home")
home_kinds = {category["kind"] for category in home_categories}
home_contract = {
    "index.html": {
        "title": "<title>Hung-Chun Tsui | Mathematics</title>",
        "publications": 'href="publications.html">All publications →</a>',
        "activities": 'href="activities.html">All activities →</a>',
    },
    "zh/index.html": {
        "title": "<title>崔鴻竣｜數學</title>",
        "publications": 'href="publications.html">所有論文 →</a>',
        "activities": 'href="activities.html">所有活動 →</a>',
    },
}
for rel, labels in home_contract.items():
    text = (ROOT / rel).read_text(encoding="utf-8")
    required_fragments = [labels["title"]]
    if home_kinds & {"featured_publications", "upcoming"}:
        required_fragments.append('class="container home-overview-grid')
    if "featured_publications" in home_kinds:
        required_fragments.extend(
            (
                'data-category-id="home-publications"',
                'id="latest-publications"',
                labels["publications"],
            )
        )
    if "upcoming" in home_kinds:
        required_fragments.extend(
            (
                'data-category-id="home-upcoming"',
                labels["activities"],
            )
        )
    if "contact" in home_kinds:
        required_fragments.extend(
            (
                'data-category-id="home-contact" id="contact"',
                'class="container split"',
            )
        )
    for fragment in required_fragments:
        if fragment not in text:
            errors.append(f"{rel}: missing legacy homepage contract {fragment!r}")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Validated {len(ids)} entries, {len(data['settings']['categories'])} categories, and {sum(len(v) for v in page_files.values())} pages.")
