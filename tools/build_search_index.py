#!/usr/bin/env python3
"""Build the bilingual client-side search index for the public website."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import process_request as core
from category_config import categories_for_page, migrate_category_data, normalized_pages

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "content" / "site.json"
OUTPUT = ROOT / "content" / "search-index.json"


def plain(value: Any, lang: str = "en") -> str:
    if isinstance(value, dict):
        value = value.get(lang) or value.get("en") or value.get("zh") or ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def entry_title(item: dict[str, Any], lang: str) -> str:
    for field in ("title", "course_title", "course", "name", "label"):
        value = plain(item.get(field), lang)
        if value:
            return value
    return str(item.get("id") or "")


def description(item: dict[str, Any], lang: str) -> str:
    parts = []
    for field in ("authors", "venue", "event", "organization", "description", "visit_description", "city", "country", "term"):
        value = plain(item.get(field), lang)
        if value and value not in parts:
            parts.append(value)
    return " · ".join(parts)[:320]


def all_records(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("activities", "honors", "publications", "teaching", "profile_items"):
        rows.extend(item for item in data.get(key, []) if isinstance(item, dict))
    return rows


def build_index() -> dict[str, Any]:
    data = migrate_category_data(core.migrate_data(json.loads(SITE.read_text(encoding="utf-8"))))
    pages = normalized_pages(data)
    page_by_id = {str(page.get("id") or ""): page for page in pages}
    category_by_id = {
        str(category.get("id") or ""): category
        for page in pages
        for category in categories_for_page(data, str(page.get("id") or ""))
    }
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(lang: str, title: str, desc: str, url: str, kind: str) -> None:
        title = re.sub(r"\s+", " ", title).strip()
        desc = re.sub(r"\s+", " ", desc).strip()
        if not title or not url:
            return
        key = (lang, title.casefold(), url)
        if key in seen:
            return
        seen.add(key)
        rows.append({"language": lang, "title": title, "description": desc, "url": "/" + url.lstrip("/"), "kind": kind})

    for page in pages:
        for lang in ("en", "zh"):
            path = str((page.get("path") or {}).get(lang) or "")
            if not path:
                continue
            header = page.get("header") if isinstance(page.get("header"), dict) else {}
            add(lang, plain((header or {}).get("title") or page.get("name"), lang), plain((header or {}).get("intro"), lang), path, "page")
            for category in categories_for_page(data, str(page.get("id") or "")):
                add(lang, plain(category.get("title"), lang), plain(category.get("intro"), lang), f"{path}#{category.get('id')}", "section")

    for item in all_records(data):
        category = category_by_id.get(str(item.get("category_id") or ""))
        page_id = str((category or {}).get("page_id") or "")
        if not page_id:
            item_type = str(item.get("type") or "")
            page_id = "publications" if item_type == "publication" else "teaching" if item_type == "teaching" else "activities" if item_type in {"conference", "talk", "visit", "organization"} else "cv"
        page = page_by_id.get(page_id)
        if not page:
            continue
        for lang in ("en", "zh"):
            path = str((page.get("path") or {}).get(lang) or "")
            if path:
                add(lang, entry_title(item, lang), description(item, lang), f"{path}#{item.get('id')}", str(item.get("type") or "item"))

    rows.sort(key=lambda row: (row["language"], row["kind"], row["title"].casefold()))
    return {"schema_version": 1, "items": rows}


def main() -> None:
    OUTPUT.write_text(json.dumps(build_index(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
