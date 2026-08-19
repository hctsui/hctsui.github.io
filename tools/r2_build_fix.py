#!/usr/bin/env python3
"""Protect external media URLs and keep homepage Upcoming out of Activities."""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

_ABSOLUTE_URL = re.compile(r"https?://[^\s\"'<>]+", flags=re.I)
_ACTIVITY_PAGE_KINDS = {"visit", "talk", "conference", "organization"}
_ACTIVITY_HTML_PATHS = ("activities.html", "zh/activities.html")


def apply_static_asset_paths_safely(
    original: Callable[[str, str], str],
    text: str,
    lang: str,
) -> str:
    """Run the existing local migration without touching complete HTTP(S) URLs."""
    protected: dict[str, str] = {}

    def stash(match: re.Match[str]) -> str:
        token = f"__HCTSUI_ABSOLUTE_MEDIA_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    result = original(_ABSOLUTE_URL.sub(stash, text), lang)
    for token, url in protected.items():
        result = result.replace(token, url)
    return result


def _upcoming_ids(module: Any, data: dict[str, Any], today: date) -> set[str]:
    return {
        str(item.get("id") or "")
        for item in module.homepage_activities(data, today)
        if item.get("id")
    }


def _source_id(item: dict[str, Any]) -> str:
    """Return the real CMS entry ID, including for display-placement copies."""
    return str(item.get("_source_id") or item.get("id") or "")


def filter_upcoming_from_activities(
    module: Any,
    data: dict[str, Any],
    category: dict[str, Any],
    today: date,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Exclude exactly the entries currently rendered as homepage Upcoming."""
    if str(category.get("page_id") or "") != "activities":
        return items
    if str(category.get("kind") or "") not in _ACTIVITY_PAGE_KINDS:
        return items

    upcoming = _upcoming_ids(module, data, today)
    if not upcoming:
        return items
    return [item for item in items if _source_id(item) not in upcoming]


def _article_markers(text: str, source_id: str) -> list[str]:
    """Find exact and display-placement article IDs for one CMS source entry."""
    pattern = re.compile(
        r'data-entry-id="(' + re.escape(source_id) + r'(?:--at--[^"<>]+)?)"'
    )
    return list(dict.fromkeys(match.group(1) for match in pattern.finditer(text)))


def _remove_article(text: str, entry_id: str) -> str:
    marker = f'data-entry-id="{entry_id}"'
    while marker in text:
        marker_at = text.find(marker)
        start = text.rfind("<article", 0, marker_at)
        end = text.find("</article>", marker_at)
        if start < 0 or end < 0:
            raise RuntimeError(
                f"Could not safely remove Upcoming entry {entry_id!r} from Activities HTML."
            )
        text = text[:start] + text[end + len("</article>") :]
    return text


def clean_generated_activity_pages(
    module: Any,
    data: dict[str, Any],
    today: date,
) -> list[Path]:
    """Remove homepage Upcoming entries from both generated Activities pages."""
    upcoming = _upcoming_ids(module, data, today)
    if not upcoming:
        return []

    changed: list[Path] = []
    root = Path(module.ROOT)
    for relative in _ACTIVITY_HTML_PATHS:
        path = root / relative
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = old
        for source_id in sorted(upcoming):
            for rendered_id in _article_markers(new, source_id):
                new = _remove_article(new, rendered_id)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(path)

        # Never silently ship a page that still duplicates homepage Upcoming.
        remaining = [
            source_id
            for source_id in sorted(upcoming)
            if _article_markers(new, source_id)
        ]
        if remaining:
            raise RuntimeError(
                f"Upcoming entries still present in {relative}: "
                + ", ".join(remaining)
            )
    return changed

def patch_build_site(module: Any) -> None:
    """Patch build_site once; unrelated rendering behavior remains unchanged."""
    if getattr(module, "_r2_absolute_media_urls_patched", False):
        return

    original_static_paths = module.apply_static_asset_paths
    original_category_items = module.category_items
    original_build = module.build

    def apply_static_asset_paths(text: str, lang: str) -> str:
        return apply_static_asset_paths_safely(original_static_paths, text, lang)

    def category_items(
        data: dict[str, Any],
        category: dict[str, Any],
        today: date,
    ) -> list[dict[str, Any]]:
        items = original_category_items(data, category, today)
        return filter_upcoming_from_activities(
            module,
            data,
            category,
            today,
            items,
        )

    def build(today: date, update_date: bool = True):
        paths = list(original_build(today, update_date))
        # Use exactly the same migrated homepage configuration as build_site.
        cleaned = clean_generated_activity_pages(module, module.load_data(), today)
        for path in cleaned:
            if path not in paths:
                paths.append(path)
        return paths

    module.apply_static_asset_paths = apply_static_asset_paths
    module.category_items = category_items
    module.build = build
    module._r2_absolute_media_urls_patched = True
