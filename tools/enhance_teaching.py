#!/usr/bin/env python3
"""Render role- and institution-aware teaching sections for website and CV.

The existing build_site.py and build_cv.py remain untouched. Run this script
immediately after both builders; it replaces only their managed TEACHING blocks.
Old entries without role/institution remain Teaching Assistant entries at NTHU.
"""

from __future__ import annotations

import html
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}

DEFAULT_ROLE = {"en": "Teaching Assistant", "zh": "助教"}
DEFAULT_INSTITUTION = {"en": "NTHU", "zh": "國立清華大學"}


def pair(entry: dict[str, Any], field: str, lang: str, default: dict[str, str] | None = None) -> str:
    value = entry.get(field)
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    if value:
        return str(value)
    if default:
        return default.get(lang) or default.get("en") or ""
    return ""


def latex_escape(value: Any) -> str:
    text = html.unescape(str(value or "")).replace("–", "--").replace("—", "---")
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def replace_html_block(path: Path, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- CMS:TEACHING:START -->", "<!-- CMS:TEACHING:END -->"
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)({re.escape(end)})", re.S)
    updated, count = pattern.subn(lambda m: m.group(1) + content.rstrip() + "\n" + m.group(3), text, count=1)
    if count != 1:
        raise RuntimeError(f"Missing or duplicated teaching marker in {path}")
    path.write_text(updated, encoding="utf-8")


def replace_tex_block(path: Path, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    start, end = "% CMS:TEACHING:START", "% CMS:TEACHING:END"
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)({re.escape(end)})", re.S)
    updated, count = pattern.subn(lambda m: m.group(1) + content.rstrip() + "\n" + m.group(3), text, count=1)
    if count != 1:
        raise RuntimeError(f"Missing or duplicated CV teaching marker in {path}")
    path.write_text(updated, encoding="utf-8")


def render_html(entry: dict[str, Any], lang: str) -> str:
    term = html.escape(pair(entry, "term", lang))
    course = html.escape(pair(entry, "course", lang))
    role = html.escape(pair(entry, "role", lang, DEFAULT_ROLE))
    institution = html.escape(pair(entry, "institution", lang, DEFAULT_INSTITUTION))
    meta = " · ".join(value for value in (role, institution) if value)
    meta_html = f'<div class="date">{meta}</div>' if meta else ""
    return (
        f'<article class="teaching-card" data-entry-id="{html.escape(str(entry["id"]))}">'
        f'<div class="date">{term}</div><h3>{course}</h3>{meta_html}</article>'
    )


def render_tex_entry(entry: dict[str, Any]) -> str:
    term = pair(entry, "term", "en")
    course = pair(entry, "course", "en")
    institution = pair(entry, "institution", "en", DEFAULT_INSTITUTION).strip()
    display_course = course
    if institution and not course.casefold().startswith(institution.casefold() + " "):
        display_course = f"{institution} {course}"
    return (
        rf"\begin{{conf}}{{{latex_escape(term)}}}" + "\n"
        + latex_escape(display_course) + "\n"
        + r"\end{conf}"
    )


def render_tex(entries: list[dict[str, Any]]) -> str:
    groups: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for entry in entries:
        role = pair(entry, "role", "en", DEFAULT_ROLE).strip() or DEFAULT_ROLE["en"]
        groups.setdefault(role, []).append(entry)

    sections: list[str] = []
    for role, group in groups.items():
        heading = (
            "\\begin{one}\n"
            f"    {{\\textbf{{\\large {latex_escape(role)}}}}}\n"
            "\\end{one}"
        )
        rows = "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_tex_entry(entry) for entry in group)
        sections.append(heading + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + rows)
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(sections)


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    entries = sorted(data.get("teaching", []), key=lambda item: int(item.get("order", 999999)))

    replace_html_block(ROOT / "teaching.html", "\n".join(render_html(entry, "en") for entry in entries))
    replace_html_block(ROOT / "zh" / "teaching.html", "\n".join(render_html(entry, "zh") for entry in entries))
    replace_tex_block(ROOT / "cv" / "Hung-Chun-Tsui-CV.tex", render_tex(entries))
    print(f"Enhanced {len(entries)} teaching entries with role and institution.")


if __name__ == "__main__":
    main()
