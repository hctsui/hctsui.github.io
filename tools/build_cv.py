#!/usr/bin/env python3
"""Generate the LaTeX CV from content/site.json without changing its design.

The template contains fixed typography/layout and invisible CMS markers. This
script replaces only the six managed CV sections and writes a compilable .tex.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
TEMPLATE_FILE = ROOT / "cv" / "Hung-Chun-Tsui-CV.template.tex"
OUTPUT_FILE = ROOT / "cv" / "Hung-Chun-Tsui-CV.tex"

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def load_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    tz = ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))
    return datetime.now(tz).date()


def latex_escape(value: Any) -> str:
    text = html_lib.unescape(str(value or ""))
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "--").replace("—", "---")
    text = text.replace("−", "-")
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def latex_url(value: Any) -> str:
    # hyperref handles common URL punctuation. Escape only TeX comment/group chars.
    text = str(value or "").strip()
    return text.replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


def rich_to_latex(value: Any, *, author: bool = False) -> str:
    """Convert the small HTML subset stored in site.json to LaTeX."""
    source = html_lib.unescape(str(value or ""))
    source = source.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")

    tokens: dict[str, str] = {}

    def token(content: str) -> str:
        key = f"@@CVTOKEN{len(tokens)}@@"
        tokens[key] = content
        return key

    def strong_repl(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1))
        wrapped = rf"\underline{{{latex_escape(inner)}}}" if author else rf"\textbf{{{latex_escape(inner)}}}"
        return token(wrapped)

    def emphasis_repl(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        escaped = latex_escape(inner)
        # Variables such as q, u, and v are better represented in math italics.
        wrapped = rf"${escaped}$" if re.fullmatch(r"[A-Za-z0-9]+", inner) else rf"\textit{{{escaped}}}"
        return token(wrapped)

    source = re.sub(r"<(?:strong|b)>(.*?)</(?:strong|b)>", strong_repl, source, flags=re.I | re.S)
    source = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", emphasis_repl, source, flags=re.I | re.S)
    source = re.sub(r"<[^>]+>", "", source)
    result = latex_escape(source)
    for key, replacement in tokens.items():
        result = result.replace(latex_escape(key), replacement)
    return result.strip()


def field_rich(entry: dict[str, Any], field: str, lang: str = "en", *, author: bool = False) -> str:
    rich = entry.get(f"{field}_html", {})
    if isinstance(rich, dict) and rich.get(lang):
        return rich_to_latex(rich[lang], author=author)
    plain = entry.get(field, {})
    if isinstance(plain, dict):
        return latex_escape(plain.get(lang) or plain.get("en") or "")
    return latex_escape(plain)


def date_value(value: str) -> date:
    return date.fromisoformat(value)


def display_date(value: str) -> str:
    d = date_value(value)
    return f"{d.year}/{d.month}/{d.day}"


def display_range(entry: dict[str, Any]) -> str:
    start = str(entry.get("start_date", ""))
    end = str(entry.get("end_date") or start)
    if not start:
        return latex_escape(entry.get("year", ""))
    if end == start:
        return display_date(start)
    return f"{display_date(start)} -- {display_date(end)}"


def activity_is_upcoming(entry: dict[str, Any], today: date) -> bool:
    if not entry.get("show_upcoming"):
        return False
    end = str(entry.get("end_date") or entry.get("start_date") or "")
    return bool(end and date_value(end) >= today)


def linked_bold(title: str, url: str) -> str:
    content = rf"\textbf{{{title}}}"
    if not url:
        return content
    return rf"\hrefWithoutArrow{{{latex_url(url)}}}{{{content}}}"


def render_activity(entry: dict[str, Any], *, kind: str) -> str:
    title = field_rich(entry, "title")
    url = str(entry.get("url", "")).strip()
    description = field_rich(entry, "description")
    date_text = display_range(entry)

    title_line = linked_bold(title, url)
    if kind == "talk" and entry.get("slides_url"):
        title_line += (
            r" {\color{secondaryColor}["
            + rf"\hrefWithoutArrow{{{latex_url(entry['slides_url'])}}}{{slides}}"
            + "]}"
        )

    body = title_line
    if description:
        body += r"\\" + description
    return (
        rf"\begin{{conf}}{{{date_text}}}" + "\n"
        + body + "\n"
        + r"\end{conf}"
    )


def publication_links(entry: dict[str, Any]) -> str:
    preferred = {"PDF": 0, "arXiv": 1, "Journal": 2, "DOI": 3, "Code": 4}
    links = [link for link in entry.get("links", []) if link.get("url")]
    links.sort(key=lambda link: preferred.get((link.get("label") or {}).get("en", ""), 99))
    rendered: list[str] = []
    for link in links:
        label = str((link.get("label") or {}).get("en") or "Link")
        display = {"PDF": "pdf", "Journal": "journal", "Code": "code"}.get(label, label)
        rendered.append(rf"\hrefWithoutArrow{{{latex_url(link['url'])}}}{{{latex_escape(display)}}}")
    if not rendered:
        return ""
    return r" {\color{secondaryColor}[" + "|".join(rendered) + "]}"


def publication_status(entry: dict[str, Any]) -> str:
    venue_plain = entry.get("venue", {})
    venue = ""
    if isinstance(venue_plain, dict):
        venue = str(venue_plain.get("en") or "").strip()
    elif venue_plain:
        venue = str(venue_plain).strip()
    year = str(entry.get("year", ""))
    if not venue or venue.lower().startswith("arxiv:"):
        return rf"\textit{{Submitted}}, {latex_escape(year)}."
    return rf"\textit{{{latex_escape(venue)}}}, {latex_escape(year)}."


def render_publication(entry: dict[str, Any], number: int) -> str:
    authors = field_rich(entry, "authors", author=True)
    title = field_rich(entry, "title")
    links = publication_links(entry)
    return (
        rf"\begin{{pub}}{{{authors}}}" + "\n"
        + rf"{{[{number}]}} \textbf{{{title}}}{links} \\" + "\n"
        + publication_status(entry) + "\n"
        + r"\end{pub}"
    )


def render_honor(entry: dict[str, Any]) -> str:
    title = field_rich(entry, "title")
    org = field_rich(entry, "organization")
    url = str(entry.get("url", "")).strip()
    body = linked_bold(title, url)
    if org:
        body += r"\\" + org
    return (
        rf"\begin{{conf}}{{{latex_escape(entry.get('year', ''))}}}" + "\n"
        + body + "\n"
        + r"\end{conf}"
    )


def render_teaching(entry: dict[str, Any]) -> str:
    term = entry.get("term", {})
    course = entry.get("course", {})
    term_en = str(term.get("en") if isinstance(term, dict) else term or "")
    course_en = str(course.get("en") if isinstance(course, dict) else course or "")
    if course_en and not course_en.upper().startswith("NTHU "):
        course_en = "NTHU " + course_en
    return (
        rf"\begin{{conf}}{{{latex_escape(term_en)}}}" + "\n"
        + latex_escape(course_en) + "\n"
        + r"\end{conf}"
    )


def replace_block(text: str, marker: str, content: str) -> str:
    start = f"% CMS:{marker}:START"
    end = f"% CMS:{marker}:END"
    pattern = re.compile(rf"({re.escape(start)}\n)(.*?)({re.escape(end)})", re.S)
    updated, count = pattern.subn(lambda match: match.group(1) + content.rstrip() + "\n" + match.group(3), text, count=1)
    if count != 1:
        raise RuntimeError(f"Missing or duplicated CV marker: {marker}")
    return updated


def build(today: date) -> Path:
    data = load_data()
    activities = data.get("activities", [])
    archived = [entry for entry in activities if not activity_is_upcoming(entry, today)]

    visits = sorted(
        [entry for entry in archived if entry.get("type") == "visit"],
        key=lambda entry: (entry.get("start_date", ""), entry.get("id", "")),
        reverse=True,
    )
    talks = sorted(
        [entry for entry in archived if entry.get("type") == "talk"],
        key=lambda entry: (entry.get("start_date", ""), entry.get("id", "")),
    )
    conferences = sorted(
        [entry for entry in archived if entry.get("type") == "conference"],
        key=lambda entry: (entry.get("start_date", ""), entry.get("id", "")),
    )
    honors = sorted(
        data.get("honors", []),
        key=lambda entry: (int(entry.get("year", 0)), -int(entry.get("order", 999999))),
    )
    publications = sorted(
        data.get("publications", []),
        key=lambda entry: (entry.get("date", ""), int(entry.get("order", 999999))),
    )
    teaching = sorted(data.get("teaching", []), key=lambda entry: int(entry.get("order", 999999)))

    blocks = {
        "PUBLICATIONS": "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(
            render_publication(entry, index) for index, entry in enumerate(publications, 1)
        ),
        "VISITS": "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_activity(entry, kind="visit") for entry in visits),
        "TALKS": "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_activity(entry, kind="talk") for entry in talks),
        "HONORS": "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_honor(entry) for entry in honors),
        "CONFERENCES": "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(
            render_activity(entry, kind="conference") for entry in conferences
        ),
        "TEACHING": (
            "\\begin{one}\n    {\\textbf{\\large Teaching Assistant}}\n\\end{one}\n"
            "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n"
            + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(render_teaching(entry) for entry in teaching)
        ),
    }

    text = TEMPLATE_FILE.read_text(encoding="utf-8")
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    text = text.replace(
        "__CV_LAST_UPDATED__",
        f"{month_names[today.month - 1]} {today.day}, {today.year}",
    )
    for marker, content in blocks.items():
        text = replace_block(text, marker, content)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(text, encoding="utf-8")
    return OUTPUT_FILE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today", help="Override site date using YYYY-MM-DD")
    args = parser.parse_args()
    data = load_data()
    output = build(site_today(data, args.today))
    print(f"Generated {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
