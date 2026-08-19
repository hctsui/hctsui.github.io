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
    return [
        item
        for item in items
        if str(item.get("id") or "") not in upcoming
    ]


def _remove_article(text: str, entry_id: str) -> str:
    """Remove timeline articles for one exact data-entry-id without parsing HTML."""
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
) -> None:
    """Final safety pass after build_site has rendered the website.

    This is deliberately limited to the two Activities HTML files.  It does not
    mutate site.json, homepage settings, CV data, ordering, categories, or any
    other generated page.
    """
    upcoming = _upcoming_ids(module, data, today)
    if not upcoming:
        return

    root = Path(module.ROOT)
    for relative in _ACTIVITY_HTML_PATHS:
        path = root / relative
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = old
        for entry_id in upcoming:
            new = _remove_article(new, entry_id)
        if new != old:
            path.write_text(new, encoding="utf-8")


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
        paths = original_build(today, update_date)
        # Reload through build_site's normal migration path so the fallback
        # uses exactly the same homepage configuration as the renderer.
        clean_generated_activity_pages(module, module.load_data(), today)
        return paths

    module.apply_static_asset_paths = apply_static_asset_paths
    module.category_items = category_items
    module.build = build
    module._r2_absolute_media_urls_patched = True
