#!/usr/bin/env python3
"""Render dynamic publication and teaching section headings for web and CV."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import build_cv
import build_site
import process_request_v4 as groups

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def pair(entry: dict[str, Any], field: str, lang: str, fallback: str = "") -> str:
    value = entry.get(field)
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or fallback)
    return str(value or fallback)


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
        section_label = "稿件類型" if lang == "zh" else "Manuscript type"
        rows = "\n".join(build_site.render_publication_li(entry, lang) for entry in entries)
        sections.append(
            f'<section class="teaching-group" data-group-id="{esc(group.get("id"))}">'
            f'<p class="section-label">{esc(section_label)}</p>'
            f'<h2>{esc(label)}</h2>'
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
            role = pair(entry, "role", lang, "助教" if lang == "zh" else "Teaching Assistant")
            cards.append(
                f'<article class="teaching-card" data-entry-id="{esc(entry.get("id"))}">'
                f'<div class="date">{esc(term)}</div>'
                f'<div><h3>{esc(course)}</h3><p class="venue">{esc(role)}</p></div>'
                f'</article>'
            )
        sections.append(
            f'<section class="teaching-group" data-group-id="{esc(group.get("id"))}">'
            f'<p class="section-label">{"機構" if lang == "zh" else "Institution"}</p>'
            f'<h2>{esc(heading)}</h2>'
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


def cv_publications(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    number = 1
    for group in sorted_groups(data, "publication"):
        entries = entries_for(data, "publication", str(group.get("id")))
        if not entries:
            continue
        heading = (
            "\\begin{one}\n"
            f"    {{\\textbf{{\\large {build_cv.latex_escape(groups.group_label(group, 'en'))}}}}}\n"
            "\\end{one}"
        )
        rows: list[str] = []
        for entry in entries:
            rows.append(build_cv.render_publication(entry, number))
            number += 1
        chunks.append(heading + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(rows))
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(chunks)


def cv_teaching(data: dict[str, Any]) -> str:
    chunks: list[str] = []
    for group in sorted_groups(data, "teaching"):
        entries = entries_for(data, "teaching", str(group.get("id")))
        if not entries:
            continue
        heading = (
            "\\begin{one}\n"
            f"    {{\\textbf{{\\large {build_cv.latex_escape(groups.group_label(group, 'en'))}}}}}\n"
            "\\end{one}"
        )
        rows: list[str] = []
        for entry in entries:
            term = pair(entry, "term", "en")
            course = pair(entry, "course", "en")
            role = pair(entry, "role", "en", "Teaching Assistant")
            rows.append(
                f"\\begin{{conf}}{{{build_cv.latex_escape(term)}}}\n"
                f"{build_cv.latex_escape(course)} \\\\\n"
                f"{{\\small\\textit{{{build_cv.latex_escape(role)}}}}}\n"
                "\\end{conf}"
            )
        chunks.append(heading + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(rows))
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(chunks)


def replace_tex(path: Path, marker: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = f"% CMS:{marker}:START"
    end = f"% CMS:{marker}:END"
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)({re.escape(end)})", re.S)
    updated, count = pattern.subn(lambda m: m.group(1) + content.rstrip() + "\n" + m.group(3), text, count=1)
    if count != 1:
        raise RuntimeError(f"Missing or duplicated CV marker: {marker}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    data = groups.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    replace_page_section(ROOT / "publications.html", "PUBLICATIONS", publication_web(data, "en"))
    replace_page_section(ROOT / "zh" / "publications.html", "PUBLICATIONS", publication_web(data, "zh"))
    replace_page_section(ROOT / "teaching.html", "TEACHING", teaching_web(data, "en"))
    replace_page_section(ROOT / "zh" / "teaching.html", "TEACHING", teaching_web(data, "zh"))
    cv_path = ROOT / "cv" / "Hung-Chun-Tsui-CV.tex"
    replace_tex(cv_path, "PUBLICATIONS", cv_publications(data))
    replace_tex(cv_path, "TEACHING", cv_teaching(data))
    print("Rendered dynamic publication and teaching groups for website and CV.")


if __name__ == "__main__":
    main()
