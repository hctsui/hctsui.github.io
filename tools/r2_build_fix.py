#!/usr/bin/env python3
"""Protect external media URLs and keep homepage Upcoming out of Activities."""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from typing import Any

_ABSOLUTE_URL = re.compile(r"https?://[^\s\"'<>]+", flags=re.I)
_ACTIVITY_PAGE_KINDS = {"visit", "talk", "conference", "organization"}


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


def filter_upcoming_from_activities(
    module: Any,
    data: dict[str, Any],
    category: dict[str, Any],
    today: date,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Exclude exactly the entries currently rendered as homepage Upcoming.

    The homepage remains the single source of truth for what counts as
    ``Upcoming``.  Once an entry expires according to homepage_activities(),
    the daily rebuild automatically stops excluding it here, so it appears
    in Activities without mutating site.json or changing the CMS workflow.
    """
    if str(category.get("page_id") or "") != "activities":
        return items
    if str(category.get("kind") or "") not in _ACTIVITY_PAGE_KINDS:
        return items

    upcoming_ids = {
        str(item.get("id") or "")
        for item in module.homepage_activities(data, today)
        if item.get("id")
    }
    if not upcoming_ids:
        return items

    return [
        item
        for item in items
        if str(item.get("id") or "") not in upcoming_ids
    ]


def patch_build_site(module: Any) -> None:
    """Patch build_site once; all unrelated rendering behavior remains unchanged."""
    if getattr(module, "_r2_absolute_media_urls_patched", False):
        return

    original_static_paths = module.apply_static_asset_paths
    original_category_items = module.category_items

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

    module.apply_static_asset_paths = apply_static_asset_paths
    module.category_items = category_items
    module._r2_absolute_media_urls_patched = True
