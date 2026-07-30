#!/usr/bin/env python3
"""Generate a category-based entry-ID catalog for edit/remove forms."""
from __future__ import annotations

import json
from pathlib import Path

from category_config import all_items, migrate_category_data, normalized_pages

ROOT = Path(__file__).resolve().parents[1]
data = migrate_category_data(json.loads((ROOT / "content/site.json").read_text(encoding="utf-8")))
category_map = {c["id"]: c for c in data["settings"]["categories"]}
page_map = {p["id"]: p for p in normalized_pages(data)}
lines = [
    "# Website content catalog / 網站內容目錄",
    "",
    "這個檔案由程式自動產生。所有項目都依照其頁面與類別列出；需要編輯或刪除時，複製最右欄的 `Entry ID`。",
    "",
]


def clean(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def item_title(item: dict, lang: str) -> str:
    for field in ("title", "course"):
        value = item.get(field)
        if isinstance(value, dict) and value.get(lang):
            return str(value[lang])
    return ""


items = all_items(data)
for page in sorted(page_map.values(), key=lambda p: p.get("order", 999)):
    page_categories = sorted(
        [c for c in category_map.values() if c.get("page_id") == page["id"]],
        key=lambda c: (int(c.get("order", 999)), c["id"]),
    )
    if not page_categories:
        continue
    lines.extend([f"## {page['name']['en']} / {page['name']['zh']}", ""])
    for category in page_categories:
        rows = sorted(
            [item for item in items if item.get("category_id") == category["id"]],
            key=lambda item: (int(item.get("order", 999999)), str(item.get("id", ""))),
        )
        if not rows:
            continue
        lines.extend([f"### {category['title']['en']} / {category['title']['zh']}", "", "| Type | English title | 中文名稱 | Entry ID |", "|---|---|---|---|"])
        for item in rows:
            lines.append(f"| {clean(item.get('type'))} | {clean(item_title(item, 'en'))} | {clean(item_title(item, 'zh'))} | `{clean(item.get('id'))}` |")
        lines.append("")

(ROOT / "CONTENT-CATALOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
