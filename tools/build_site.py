#!/usr/bin/env python3
"""Render managed website content without changing the site's layout or CSS.

The script replaces only content inside invisible CMS markers already present in
HTML files. Everything outside those markers is left byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
PAGE_FILES = [
    ROOT / "index.html",
    ROOT / "cv.html",
    ROOT / "publications.html",
    ROOT / "activities.html",
    ROOT / "teaching.html",
    ROOT / "zh" / "index.html",
    ROOT / "zh" / "cv.html",
    ROOT / "zh" / "publications.html",
    ROOT / "zh" / "activities.html",
    ROOT / "zh" / "teaching.html",
]


def load_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    tz = ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))
    return datetime.now(tz).date()


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def inline_value(entry: dict[str, Any], field: str, lang: str) -> str:
    rich = entry.get(f"{field}_html", {})
    if isinstance(rich, dict) and rich.get(lang):
        return str(rich[lang])
    plain = entry.get(field, {})
    if isinstance(plain, dict):
        return esc(plain.get(lang) or "")
    return esc(plain)


def plain_value(entry: dict[str, Any], field: str, lang: str) -> str:
    plain = entry.get(field, {})
    if isinstance(plain, dict):
        return str(plain.get(lang) or "")
    return str(plain or "")


def date_value(value: str) -> date:
    return date.fromisoformat(value)


def display_date(value: str) -> str:
    d = date_value(value)
    return f"{d.year}/{d.month}/{d.day}"


def display_range(entry: dict[str, Any]) -> str:
    start = str(entry.get("start_date", ""))
    end = str(entry.get("end_date") or start)
    if not start:
        return str(entry.get("year", ""))
    if end == start:
        return display_date(start)
    return f"{display_date(start)}–{display_date(end)}"


def activity_is_upcoming(entry: dict[str, Any], today: date) -> bool:
    if not entry.get("show_upcoming"):
        return False
    end = str(entry.get("end_date") or entry.get("start_date") or "")
    return bool(end and date_value(end) >= today)


def link_or_text(content: str, url: str) -> str:
    if not url:
        return content
    return f'<a href="{esc(url)}" rel="noopener" target="_blank">{content}</a>'


def render_activity(entry: dict[str, Any], lang: str) -> str:
    title = inline_value(entry, "title", lang)
    heading = link_or_text(title, str(entry.get("url", "")))
    description = inline_value(entry, "description", lang)
    slides = str(entry.get("slides_url", ""))
    links = ""
    if slides:
        label = "投影片" if lang == "zh" else "Slides"
        links = (
            '<div class="pub-links">'
            f'<a href="{esc(slides)}" rel="noopener" target="_blank">{label}</a>'
            "</div>"
        )
    paragraph = f"<p>{description}</p>" if description else ""
    return (
        f'<article class="timeline-item" data-entry-id="{esc(entry["id"])}">'
        f"<time>{display_range(entry)}</time><div><h3>{heading}</h3>"
        f"{paragraph}{links}</div></article>"
    )


def render_honor(entry: dict[str, Any], lang: str) -> str:
    title = link_or_text(inline_value(entry, "title", lang), str(entry.get("url", "")))
    org = inline_value(entry, "organization", lang)
    paragraph = f"<p>{org}</p>" if org else ""
    return (
        f'<article class="timeline-item" data-entry-id="{esc(entry["id"])}">'
        f'<time>{esc(entry.get("year", ""))}</time><div><h3>{title}</h3>{paragraph}</div></article>'
    )


def render_publication_article(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    links_html = "".join(
        f'<a href="{esc(link.get("url", ""))}" rel="noopener" target="_blank">'
        f'{esc((link.get("label") or {}).get(lang) or (link.get("label") or {}).get("en") or "Link")}</a>'
        for link in entry.get("links", [])
        if link.get("url")
    )
    links = f'<div class="pub-links">{links_html}</div>' if links_html else ""
    arxiv_attr = f' data-arxiv="{esc(entry.get("arxiv", ""))}"' if entry.get("arxiv") else ""
    if homepage:
        article_open = '<article class="publication">'
        title = (entry.get("homepage_title_html", {}) or {}).get(lang) or inline_value(entry, "title", lang)
        authors = (entry.get("homepage_authors_html", {}) or {}).get(lang) or inline_value(entry, "authors", lang)
    else:
        article_open = (
            f'<article class="publication" data-entry-id="{esc(entry["id"])}"{arxiv_attr} '
            f'data-date="{esc(entry.get("date", ""))}">'
        )
        title = inline_value(entry, "title", lang)
        authors = inline_value(entry, "authors", lang)
    return (
        f'{article_open}<div class="pub-year">{esc(entry.get("year", ""))}</div><div>'
        f'<h3>{title}</h3>'
        f'<p class="authors">{authors}</p>'
        f'<p class="venue">{inline_value(entry, "venue", lang)}</p>{links}</div></article>'
    )


def render_publication_li(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    return f"<li>{render_publication_article(entry, lang, homepage=homepage)}</li>"


def render_teaching(entry: dict[str, Any], lang: str) -> str:
    term = esc(plain_value(entry, "term", lang))
    course = esc(plain_value(entry, "course", lang))
    return (
        f'<article class="teaching-card" data-entry-id="{esc(entry["id"])}">'
        f'<div class="date">{term}</div><h3>{course}</h3></article>'
    )


def replace_block(text: str, marker: str, content: str) -> tuple[str, bool]:
    start = f"<!-- CMS:{marker}:START -->"
    end = f"<!-- CMS:{marker}:END -->"
    if start not in text or end not in text:
        raise RuntimeError(f"Missing CMS marker {marker}")
    before, rest = text.split(start, 1)
    old, after = rest.split(end, 1)
    # Newlines make source readable but have no visual effect.
    new_inner = "\n" + content.rstrip() + "\n"
    new_text = before + start + new_inner + end + after
    return new_text, old != new_inner


def update_footer(text: str, lang: str, today: date) -> str:
    formatted = f"{today.year}/{today.month}/{today.day}"
    if lang == "zh":
        replacement = f"<p>最後更新：{formatted}</p>"
        pattern = r"<p>最後更新：[^<]*</p>"
    else:
        replacement = f"<p>Last updated: {formatted}</p>"
        pattern = r"<p>Last updated:[^<]*</p>"
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Could not find footer update line")
    return updated


def join_lines(items: list[str]) -> str:
    return "\n".join(items)


def ordered_ungrouped(data: dict[str, Any], kind: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order_ids = data.get("settings", {}).get("entry_order", {}).get(kind, [])
    if isinstance(order_ids, list) and order_ids:
        rank = {str(entry_id): index for index, entry_id in enumerate(order_ids)}
        return sorted(entries, key=lambda entry: (rank.get(str(entry.get("id")), 999999), str(entry.get("id", ""))))
    if kind == "honor":
        return sorted(entries, key=lambda entry: (-int(entry.get("year", 0)), int(entry.get("order", 999999)), str(entry.get("id", ""))))
    return sorted(entries, key=lambda entry: (entry.get("start_date", ""), entry.get("id", "")), reverse=True)


def build(today: date, update_date: bool = True) -> list[Path]:
    data = load_data()
    activities = data.get("activities", [])
    honors = data.get("honors", [])
    publications = data.get("publications", [])
    teaching = data.get("teaching", [])

    upcoming = sorted(
        [e for e in activities if activity_is_upcoming(e, today)],
        key=lambda e: (e.get("start_date", ""), e.get("id", "")),
    )
    archived = [e for e in activities if not activity_is_upcoming(e, today)]
    visits = ordered_ungrouped(data, "visit", [e for e in archived if e.get("type") == "visit"])
    talks = ordered_ungrouped(data, "talk", [e for e in archived if e.get("type") == "talk"])
    conferences = ordered_ungrouped(data, "conference", [e for e in archived if e.get("type") == "conference"])
    honors_sorted = ordered_ungrouped(data, "honor", honors)
    publications_sorted = sorted(
        publications,
        key=lambda e: (e.get("date", ""), int(e.get("order", 999999))),
    )
    latest = sorted(
        publications,
        key=lambda e: (e.get("date", ""), e.get("id", "")),
        reverse=True,
    )[: int(data.get("settings", {}).get("homepage_publication_limit", 2))]
    teaching_sorted = sorted(teaching, key=lambda e: int(e.get("order", 999999)))

    page_blocks: dict[str, dict[str, str]] = {
        "index.html": {
            "HOME_PUBLICATIONS": join_lines([render_publication_li(e, "en", homepage=True) for e in latest]),
            "UPCOMING": join_lines([render_activity(e, "en") for e in upcoming]),
        },
        "zh/index.html": {
            "HOME_PUBLICATIONS": join_lines([render_publication_li(e, "zh", homepage=True) for e in latest]),
            "UPCOMING": join_lines([render_activity(e, "zh") for e in upcoming]),
        },
        "activities.html": {
            "VISITS": join_lines([render_activity(e, "en") for e in visits]),
            "TALKS": join_lines([render_activity(e, "en") for e in talks]),
            "CONFERENCES": join_lines([render_activity(e, "en") for e in conferences]),
        },
        "zh/activities.html": {
            "VISITS": join_lines([render_activity(e, "zh") for e in visits]),
            "TALKS": join_lines([render_activity(e, "zh") for e in talks]),
            "CONFERENCES": join_lines([render_activity(e, "zh") for e in conferences]),
        },
        "cv.html": {"HONORS": join_lines([render_honor(e, "en") for e in honors_sorted])},
        "zh/cv.html": {"HONORS": join_lines([render_honor(e, "zh") for e in honors_sorted])},
        "publications.html": {
            "PUBLICATIONS": join_lines([render_publication_li(e, "en") for e in publications_sorted])
        },
        "zh/publications.html": {
            "PUBLICATIONS": join_lines([render_publication_li(e, "zh") for e in publications_sorted])
        },
        "teaching.html": {"TEACHING": join_lines([render_teaching(e, "en") for e in teaching_sorted])},
        "zh/teaching.html": {"TEACHING": join_lines([render_teaching(e, "zh") for e in teaching_sorted])},
    }

    candidates: dict[Path, str] = {}
    content_changed = False
    for rel, blocks in page_blocks.items():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        changed_here = False
        for marker, rendered in blocks.items():
            text, changed = replace_block(text, marker, rendered)
            changed_here = changed_here or changed
        candidates[path] = text
        content_changed = content_changed or changed_here

    # A content change updates the site-wide footer date consistently.
    if content_changed and update_date:
        for path in PAGE_FILES:
            text = candidates.get(path, path.read_text(encoding="utf-8"))
            lang = "zh" if path.parent.name == "zh" else "en"
            candidates[path] = update_footer(text, lang, today)

    changed_files: list[Path] = []
    for path, text in candidates.items():
        old = path.read_text(encoding="utf-8")
        if old != text:
            path.write_text(text, encoding="utf-8")
            changed_files.append(path)
    return changed_files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="Override date using YYYY-MM-DD (for testing)")
    parser.add_argument("--no-update-date", action="store_true")
    args = parser.parse_args()
    data = load_data()
    today = site_today(data, args.today)
    changed = build(today, update_date=not args.no_update_date)
    for path in changed:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
