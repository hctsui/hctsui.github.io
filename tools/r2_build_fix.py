#!/usr/bin/env python3
"""Protect external media URLs, filter homepage Upcoming, and extend course pages."""
from __future__ import annotations

import copy
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

_ABSOLUTE_URL = re.compile(r"https?://[^\s\"'<>]+", flags=re.I)
_ACTIVITY_PAGE_KINDS = {"visit", "talk", "conference", "organization"}
_ACTIVITY_HTML_PATHS = ("activities.html", "zh/activities.html")


def apply_static_asset_paths_safely(
    original: Callable[..., str],
    text: str,
    lang: str,
    page_path: str = "",
) -> str:
    """Run the existing local migration without touching complete HTTP(S) URLs."""
    protected: dict[str, str] = {}

    def stash(match: re.Match[str]) -> str:
        token = f"__HCTSUI_ABSOLUTE_MEDIA_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    protected_text = _ABSOLUTE_URL.sub(stash, text)
    result = (
        original(protected_text, lang, page_path)
        if page_path
        else original(protected_text, lang)
    )
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


COURSE_SECTION_DETAIL_PREFIX = "__course_section__:"


def _course_pair(value: Any, field: str, lang: str) -> str:
    raw = value.get(field) if isinstance(value, dict) else {}
    if isinstance(raw, dict):
        return str(raw.get(lang) or raw.get("en") or raw.get("zh") or "")
    return str(raw or "")


def _course_section_rows(page: dict[str, Any]) -> list[dict[str, Any]]:
    course = page.get("course") if isinstance(page.get("course"), dict) else {}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in course.get("details", []) if isinstance(course.get("details"), list) else []:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "")
        if not row_id.startswith(COURSE_SECTION_DETAIL_PREFIX):
            continue
        section_id = row_id[len(COURSE_SECTION_DETAIL_PREFIX):] or f"section-{len(result)+1}"
        seen.add(section_id)
        result.append({"id": section_id, "title": row.get("label"), "content": row.get("value")})
    # Compatibility with drafts made before sections were encoded into details.
    for index, row in enumerate(course.get("sections", []) if isinstance(course.get("sections"), list) else []):
        if not isinstance(row, dict):
            continue
        section_id = str(row.get("id") or f"section-{index+1}")
        if section_id in seen:
            continue
        seen.add(section_id)
        result.append(row)
    return result


def _course_page_without_section_details(page: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(page)
    course = clean.get("course") if isinstance(clean.get("course"), dict) else {}
    course["details"] = [
        row for row in course.get("details", []) if isinstance(row, dict)
        and not str(row.get("id") or "").startswith(COURSE_SECTION_DETAIL_PREFIX)
    ]
    course.pop("sections", None)
    clean["course"] = course
    return clean


def render_course_custom_sections(module: Any, page: dict[str, Any], lang: str) -> str:
    """Render user-defined course blocks without constraining their titles."""
    cards: list[str] = []
    for index, row in enumerate(_course_section_rows(page), start=1):
        title = _course_pair(row, "title", lang).strip()
        content = _course_pair(row, "content", lang).strip()
        if not title and not content:
            continue
        section_id = str(row.get("id") or f"section-{index}")
        title_html = module.rich_html(title) if title else ""
        body_html = module.rich_html(content) if content else ""
        heading = f'<h2>{title_html}</h2>' if title_html else ""
        body = f'<div class="course-content-body">{body_html}</div>' if body_html else ""
        cards.append(
            f'<article class="course-content-card" data-course-section-id="{module.esc(section_id)}">'
            f'{heading}{body}</article>'
        )
    if not cards:
        return ""
    return '<div class="course-custom-sections">' + "".join(cards) + "</div>"


def enhance_course_page(module: Any, rendered: str, page: dict[str, Any], lang: str) -> str:
    """Insert free-form blocks and a clearer schedule heading into course pages."""
    custom = render_course_custom_sections(module, page, lang)
    schedule_marker = '<div class="course-schedule-wrap">'
    if schedule_marker in rendered:
        eyebrow = "Weekly plan" if lang == "en" else "課程進度"
        title = "Schedule & Materials" if lang == "en" else "日期、主題與教材"
        heading = (
            '<div class="course-section-heading">'
            f'<span>{eyebrow}</span><h2>{title}</h2></div>'
        )
        return rendered.replace(schedule_marker, custom + heading + schedule_marker, 1)
    if custom:
        footer_marker = '<p class="course-footer-note">'
        if footer_marker in rendered:
            return rendered.replace(footer_marker, custom + footer_marker, 1)
        closing = '</div></section>'
        if closing in rendered:
            return rendered.replace(closing, custom + closing, 1)
    return rendered

def patch_build_site(module: Any) -> None:
    """Patch build_site once; unrelated rendering behavior remains unchanged."""
    if getattr(module, "_r2_absolute_media_urls_patched", False):
        return

    original_static_paths = module.apply_static_asset_paths
    original_category_items = module.category_items
    original_build = module.build
    original_course_page = getattr(module, "render_course_page", None)

    def apply_static_asset_paths(
        text: str,
        lang: str,
        page_path: str = "",
    ) -> str:
        return apply_static_asset_paths_safely(
            original_static_paths,
            text,
            lang,
            page_path,
        )

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

    def render_course_page(data: dict[str, Any], page: dict[str, Any], lang: str) -> str:
        if not callable(original_course_page):
            return ""
        rendered = original_course_page(data, _course_page_without_section_details(page), lang)
        return enhance_course_page(module, rendered, page, lang)

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
    if callable(original_course_page):
        module.render_course_page = render_course_page
    module.build = build
    module._r2_absolute_media_urls_patched = True
