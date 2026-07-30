#!/usr/bin/env python3
"""Render dynamic publication and teaching headings for the website only."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import build_site
import process_request as groups
from heading_config import heading_value

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def pair(entry: dict[str, Any], field: str, lang: str) -> str:
    value = entry.get(field)
    if isinstance(value, dict):
        return str(value.get(lang) or "")
    return str(value or "")


def sorted_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return sorted(
        groups.content_groups(data, kind),
        key=lambda group: (int(group.get("order", 999999)), str(group.get("id", ""))),
    )


def entries_for(data: dict[str, Any], kind: str, group_id: str) -> list[dict[str, Any]]:
    section = "publications" if kind == "publication" else "teaching"
    entries = [entry for entry in data.get(section, []) if entry.get("group_id") == group_id]
    return sorted(entries, key=lambda entry: (int(entry.get("order", 999999)), str(entry.get("id", ""))))


def hidden_marker(marker: str, wrapper: str) -> str:
    return (
        f'<template hidden aria-hidden="true"><{wrapper}>\n'
        f'<!-- CMS:{marker}:START -->\n'
        f'<!-- CMS:{marker}:END -->\n'
        f'</{wrapper}></template>'
    )


def publication_web(data: dict[str, Any], lang: str) -> str:
    sections: list[str] = [hidden_marker("PUBLICATIONS", "ol")]
    used = 0
    for group in sorted_groups(data, "publication"):
        entries = entries_for(data, "publication", str(group.get("id")))
        if not entries:
            continue
        used += 1
        label = groups.group_label(group, lang)
        section_label = heading_value(data, "publication_groups", "label", lang)
        rows = "\n".join(build_site.render_publication_li(entry, lang) for entry in entries)
        heading = f'<h2>{esc(label)}</h2>' if label else ""
        sections.append(
            f'<section class="teaching-group" data-group-id="{esc(group.get("id"))}">'
            f'<p class="section-label" data-heading-key="publication_groups" data-heading-part="label">{esc(section_label)}</p>'
            f'{heading}'
            f'<ol class="publication-list">{rows}</ol>'
            f'</section>'
        )
    if used == 0:
        sections.append(f'<p>{"目前沒有論文資料。" if lang == "zh" else "No publication entries yet."}</p>')
    return "\n".join(sections)


def teaching_web(data: dict[str, Any], lang: str) -> str:
    sections: list[str] = [hidden_marker("TEACHING", "div")]
    used = 0
    for group in sorted_groups(data, "teaching"):
        entries = entries_for(data, "teaching", str(group.get("id")))
        if not entries:
            continue
        used += 1
        heading = groups.group_label(group, lang)
        cards: list[str] = []
        for entry in entries:
            term = pair(entry, "term", lang)
            course = pair(entry, "course", lang)
            role = pair(entry, "role", lang)
            role_html = f'<p class="venue">{esc(role)}</p>' if role else ""
            cards.append(
                f'<article class="teaching-card" data-entry-id="{esc(entry.get("id"))}">'
                f'<div class="date">{esc(term)}</div>'
                f'<div><h3>{esc(course)}</h3>{role_html}</div>'
                f'</article>'
            )
        heading_html = f'<h2>{esc(heading)}</h2>' if heading else ""
        sections.append(
            f'<section class="teaching-group" data-group-id="{esc(group.get("id"))}">'
            f'<p class="section-label" data-heading-key="teaching_groups" data-heading-part="label">{esc(heading_value(data, "teaching_groups", "label", lang))}</p>'
            f'{heading_html}'
            f'<div class="teaching-grid">{"".join(cards)}</div>'
            f'</section>'
        )
    if used == 0:
        sections.append(f'<p>{"目前沒有教學資料。" if lang == "zh" else "No teaching entries yet."}</p>')
    return "\n".join(sections)


def replace_page_section(path: Path, marker: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    marker_pos = text.find(f"CMS:{marker}:START")
    if marker_pos < 0:
        raise RuntimeError(f"Missing {marker} marker in {path}")
    start = text.rfind('<section class="section">', 0, marker_pos)
    if start < 0:
        raise RuntimeError(f"Could not locate outer section for {marker} in {path}")
    token_pattern = re.compile(r"<section\b[^>]*>|</section>", re.I)
    depth = 0
    end = -1
    for token in token_pattern.finditer(text, start):
        if token.group(0).lower().startswith("</section"):
            depth -= 1
            if depth == 0:
                end = token.end()
                break
        else:
            depth += 1
    if end < 0:
        raise RuntimeError(f"Could not find matching outer section for {marker} in {path}")
    replacement = f'<section class="section"><div class="container">\n{content}\n</div></section>'
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def main() -> None:
    data = groups.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    replace_page_section(ROOT / "publications.html", "PUBLICATIONS", publication_web(data, "en"))
    replace_page_section(ROOT / "zh" / "publications.html", "PUBLICATIONS", publication_web(data, "zh"))
    replace_page_section(ROOT / "teaching.html", "TEACHING", teaching_web(data, "en"))
    replace_page_section(ROOT / "zh" / "teaching.html", "TEACHING", teaching_web(data, "zh"))
    print("Rendered dynamic publication and teaching groups for website.")


if __name__ == "__main__":
    main()
