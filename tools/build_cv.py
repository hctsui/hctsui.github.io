#!/usr/bin/env python3
"""Generate English and Traditional-Chinese LaTeX CVs from managed categories."""
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

import process_request as core
from category_config import category_map, items_for_category, migrate_category_data, normalized_cv_order, normalized_pages

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
TEMPLATES = {"en": ROOT / "cv/Hung-Chun-Tsui-CV.template.tex", "zh": ROOT / "cv/Hung-Chun-Tsui-CV-zh.template.tex"}
OUTPUTS = {"en": ROOT / "cv/Hung-Chun-Tsui-CV.tex", "zh": ROOT / "cv/Hung-Chun-Tsui-CV-zh.tex"}
LATEX_ESCAPES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def load_data() -> dict[str, Any]:
    return migrate_category_data(core.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8"))))


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    return datetime.now(ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))).date()


def latex_escape(value: Any) -> str:
    text = core.strip_invisible_chars(html_lib.unescape(str(value or ""))).replace("\u00a0", " ").replace("–", "--").replace("—", "---").replace("−", "-")
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in text)


def latex_url(value: Any) -> str:
    return str(core.strip_invisible_chars(str(value or ""))).strip().replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


def rich_to_latex(value: Any, *, author: bool = False, auto_math: bool = False) -> str:
    """Convert safe inline markup while preserving explicit math segments.

    Supported authoring forms: <em>x</em>, [i]x[/i], and $x$.
    This fixes category headings in the Chinese CV being escaped out of math mode.
    """
    source = str(core.strip_invisible_chars(html_lib.unescape(str(value or "")))).replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    tokens: dict[str, str] = {}

    def token(content: str) -> str:
        key = f"@@CVTOKEN{len(tokens)}@@"
        tokens[key] = content
        return key

    # Preserve explicit inline math before general LaTeX escaping.
    def math_token(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        return token(f"${inner}$")

    source = re.sub(r"\$([^$\n]+)\$", math_token, source)
    source = re.sub(r"\\\((.+?)\\\)", math_token, source)

    # Older Chinese records often stored mathematical symbols as plain Latin
    # text even when the English rich field used <em>.  Recover the common
    # mathematical forms for the Chinese CV without changing ordinary English.
    if auto_math and re.search(r"[\u3400-\u9fff]", source):
        source = re.sub(r"(?<![A-Za-z])(?:zeta)(?![A-Za-z])", lambda _: token(r"$\zeta$"), source, flags=re.I)
        source = re.sub(r"(?<![A-Za-z])(?:Gamma)(?![A-Za-z])", lambda _: token(r"$\Gamma$"), source)
        source = re.sub(r"(?<![A-Za-z])([qtuvL])(?=(?:-|\s|、|，|。|／|$))", lambda m: token(f"${m.group(1)}$"), source)

    def strong(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1))
        return token(rf"\underline{{{latex_escape(inner)}}}" if author else rf"\textbf{{{latex_escape(inner)}}}")

    def emphasis(match: re.Match[str]) -> str:
        inner = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        escaped = latex_escape(inner)
        return token(rf"${escaped}$" if re.fullmatch(r"[A-Za-z0-9_+\-]+", inner) else rf"\textit{{{escaped}}}")

    source = re.sub(r"<(?:strong|b)>(.*?)</(?:strong|b)>", strong, source, flags=re.I | re.S)
    source = re.sub(r"<(?:em|i)>(.*?)</(?:em|i)>", emphasis, source, flags=re.I | re.S)
    source = re.sub(r"\[b\](.*?)\[/b\]", strong, source, flags=re.I | re.S)
    source = re.sub(r"\[i\](.*?)\[/i\]", emphasis, source, flags=re.I | re.S)
    source = re.sub(r"<[^>]+>", "", source)
    result = latex_escape(source)
    for key, replacement in tokens.items():
        result = result.replace(latex_escape(key), replacement)
    return result.strip()


def field_rich(entry: dict[str, Any], field: str, lang: str, *, author: bool = False) -> str:
    rich = entry.get(f"{field}_html", {})
    if isinstance(rich, dict) and rich.get(lang):
        return rich_to_latex(rich[lang], author=author, auto_math=lang == "zh")
    plain = entry.get(field, {})
    if isinstance(plain, dict):
        return rich_to_latex(plain.get(lang) or plain.get("en") or plain.get("zh") or "", author=author, auto_math=lang == "zh")
    return rich_to_latex(plain, author=author, auto_math=lang == "zh")


def pair(entry: dict[str, Any], field: str, lang: str) -> str:
    value = entry.get(field)
    return str(value.get(lang) or value.get("en") or value.get("zh") or "") if isinstance(value, dict) else str(value or "")


def display_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d.year}/{d.month}/{d.day}"


def display_range(entry: dict[str, Any], lang: str) -> str:
    explicit = pair(entry, "date_label", lang).strip()
    if explicit:
        return latex_escape(explicit)
    start = str(entry.get("start_date") or "")
    end = str(entry.get("end_date") or start)
    if not start:
        return latex_escape(entry.get("year", ""))
    if end == start or not end:
        return display_date(start)
    return f"{display_date(start)} -- {display_date(end)}"


def linked_bold(title: str, url: str) -> str:
    content = rf"\textbf{{{title}}}"
    return rf"\hrefWithoutArrow{{{latex_url(url)}}}{{{content}}}" if url and title else content


def render_activity(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    title_line = linked_bold(title, str(entry.get("url") or "").strip())
    detail_lines: list[str] = []
    if entry.get("type") == "talk" and entry.get("slides_url"):
        label = "投影片" if lang == "zh" else "slides"
        detail_lines.append(
            r"{\small\color{secondaryColor}["
            + rf"\hrefWithoutArrow{{{latex_url(entry['slides_url'])}}}{{{label}}}"
            + "]}"
        )
    if entry.get("type") == "conference":
        role = field_rich(entry, "role", lang)
        if role and role.casefold() != "participant" and role != "一般參與者":
            title_line += r" \quad {\color{secondaryColor}\textit{" + role + "}}"
    description = field_rich(entry, "description", lang)
    if description:
        detail_lines.append(description)
    body = title_line + "".join(r"\\" + line for line in detail_lines)
    return rf"\begin{{conf}}{{{display_range(entry, lang)}}}" + "\n" + body + "\n" + r"\end{conf}"


def render_organization(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    body = linked_bold(title, str(entry.get("url") or "").strip())
    meta = " · ".join(x for x in (field_rich(entry, "organization_kind", lang), field_rich(entry, "role", lang)) if x)
    if meta:
        body += r"\\" + rf"\textit{{{meta}}}"
    description = field_rich(entry, "description", lang)
    if description:
        body += r"\\" + description
    return rf"\begin{{conf}}{{{display_range(entry, lang)}}}" + "\n" + body + "\n" + r"\end{conf}"


def publication_links(entry: dict[str, Any], lang: str) -> str:
    preferred = {"PDF": 0, "arXiv": 1, "Journal": 2, "DOI": 3, "Code": 4}
    links = [x for x in entry.get("links", []) if x.get("url")]
    links.sort(key=lambda x: preferred.get((x.get("label") or {}).get("en", ""), 99))
    rendered = []
    for link in links:
        labels = link.get("label") or {}
        canonical = str(labels.get("en") or "Link")
        display = str(labels.get(lang) or {"PDF": "pdf", "Journal": "journal", "Code": "code"}.get(canonical, canonical))
        rendered.append(rf"\hrefWithoutArrow{{{latex_url(link['url'])}}}{{{latex_escape(display)}}}")
    return r"{\small\color{secondaryColor}[" + " | ".join(rendered) + "]}" if rendered else ""


def render_publication(entry: dict[str, Any], number: int, lang: str) -> str:
    authors = field_rich(entry, "authors", lang, author=True)
    title = field_rich(entry, "title", lang)
    venue = pair(entry, "venue", lang).strip()
    year = str(entry.get("year") or "")
    status = (rf"\textit{{{rich_to_latex(venue)}}}, {latex_escape(year)}." if venue else latex_escape(year) + ".")
    lines = [rf"{{({number})}} \textbf{{{title}}}"]
    links = publication_links(entry, lang)
    if links:
        lines.append(links)
    if status.strip("."):
        lines.append(status)
    return rf"\begin{{pub}}{{{authors}}}" + "\n" + r"\\".join(lines) + "\n" + r"\end{pub}"


def render_honor(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    org = field_rich(entry, "organization", lang)
    body = linked_bold(title, str(entry.get("url") or "").strip())
    if org:
        body += r"\\" + org
    return rf"\begin{{conf}}{{{latex_escape(entry.get('year', ''))}}}" + "\n" + body + "\n" + r"\end{conf}"


def render_interest(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    desc = field_rich(entry, "description", lang)
    return "\\begin{one}\n" + title + (r"\\" + desc if desc else "") + "\n\\end{one}"


def render_education(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    org = field_rich(entry, "organization", lang)
    desc = field_rich(entry, "description", lang)
    body = rf"\textbf{{{org}}}" if org else ""
    if desc:
        body += r" \\" + "\n" + rf"{{\small ({desc})}}"
    return rf"\begin{{edu}}{{\textbf{{{title}}}}}{{{display_range(entry, lang)}}}" + "\n    " + body + "\n" + r"\end{edu}"


def render_teaching(entry: dict[str, Any], lang: str) -> str:
    course = field_rich(entry, "course", lang)
    term = field_rich(entry, "term", lang)
    role = field_rich(entry, "role", lang)
    return rf"\begin{{teaching}}{{{course}}}{{{term}}}" + "\n    " + role + "\n" + r"\end{teaching}"


def render_personal(items: list[dict[str, Any]], lang: str) -> str:
    rows = []
    for item in items:
        title = field_rich(item, "title", lang)
        value = field_rich(item, "description", lang)
        url = str(item.get("url") or "").strip()
        if url:
            value = rf"\hrefWithoutArrow{{{latex_url(url)}}}{{{value}}}"
        rows.append(rf"\textbf{{{title}}} & {value} \\")
    return "\\begin{one}\n    \\renewcommand{\\arraystretch}{1.2}\n    \\begin{tabular}{@{} p{3cm} @{\\hspace{0.2cm}} p{12cm} @{}}\n        " + "\n        ".join(rows) + "\n    \\end{tabular}\n\\end{one}"


def render_generic(entry: dict[str, Any], lang: str) -> str:
    title = field_rich(entry, "title", lang)
    desc = field_rich(entry, "description", lang)
    body = linked_bold(title, str(entry.get("url") or "").strip())
    if desc:
        body += r"\\" + desc
    return rf"\begin{{conf}}{{{display_range(entry, lang)}}}" + "\n" + body + "\n" + r"\end{conf}"


def activity_finished(entry: dict[str, Any], today: date) -> bool:
    """CV activity rows appear only after their final calendar day has passed."""
    if entry.get("type") not in {"visit", "talk", "conference", "organization"}:
        return True
    value = str(entry.get("end_date") or entry.get("start_date") or "").strip()
    if not value:
        return True
    try:
        return date.fromisoformat(value) < today
    except ValueError:
        return True


def cv_items_for_category(data: dict[str, Any], category: dict[str, Any], today: date) -> list[dict[str, Any]]:
    return [item for item in items_for_category(data, category["id"]) if activity_finished(item, today)]


def render_category_rows(
    data: dict[str, Any],
    category: dict[str, Any],
    lang: str,
    today: date,
    publication_start: int = 1,
) -> tuple[list[str], int]:
    items = cv_items_for_category(data, category, today)
    if not items:
        return [], publication_start
    kind = category["kind"]
    rows: list[str] = []
    if kind == "publication":
        rows = [render_publication(item, i, lang) for i, item in enumerate(items, publication_start)]
        publication_start += len(rows)
    elif kind in {"visit", "talk", "conference"}:
        rows = [render_activity(item, lang) for item in items]
    elif kind == "organization":
        rows = [render_organization(item, lang) for item in items]
    elif kind == "honor":
        rows = [render_honor(item, lang) for item in items]
    elif kind == "interest":
        rows = [render_interest(item, lang) for item in items]
    elif kind == "education":
        rows = [render_education(item, lang) for item in items]
    elif kind == "teaching":
        rows = [render_teaching(item, lang) for item in items]
    elif kind == "personal":
        rows = [render_personal(items, lang)]
    else:
        rows = [render_generic(item, lang) for item in items]
    return rows, publication_start


def render_category(
    data: dict[str, Any],
    category: dict[str, Any],
    lang: str,
    today: date | None = None,
) -> str:
    today = today or site_today(data)
    rows, _ = render_category_rows(data, category, lang, today)
    if not rows:
        return ""
    title = rich_to_latex(category.get("title", {}).get(lang, ""), auto_math=lang == "zh")
    return rf"\section{{{title}}}" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(rows)


def page_heading(data: dict[str, Any], page_id: str, lang: str) -> str:
    page = next((item for item in normalized_pages(data) if item["id"] == page_id), None)
    value = page.get("header", {}).get("title", {}).get(lang, "") if page else ""
    return rich_to_latex(value, auto_math=lang == "zh")


def render_grouped_categories(
    data: dict[str, Any],
    categories: list[dict[str, Any]],
    lang: str,
    today: date,
) -> str:
    if not categories:
        return ""
    page_id = str(categories[0].get("page_id") or "")
    section_title = page_heading(data, page_id, lang)
    groups: list[str] = []
    publication_number = 1
    for category in categories:
        rows, publication_number = render_category_rows(
            data,
            category,
            lang,
            today,
            publication_number,
        )
        if not rows:
            continue
        title = rich_to_latex(category.get("title", {}).get(lang, ""), auto_math=lang == "zh")
        groups.append(rf"\cvgroup{{{title}}}" + "\n" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(rows))
    if not groups:
        return ""
    return rf"\section{{{section_title}}}" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(groups)


def build_sections(data: dict[str, Any], lang: str, today: date | None = None) -> str:
    today = today or site_today(data)
    cmap = category_map(data)
    ordered = [
        cmap[cid]
        for cid in normalized_cv_order(data)
        if cid in cmap and cmap[cid].get("show_on_cv")
    ]
    chunks = []
    consumed: set[str] = set()
    for category in ordered:
        if category["id"] in consumed:
            continue
        if category["kind"] in {"publication", "teaching"}:
            grouped = [item for item in ordered if item["kind"] == category["kind"]]
            consumed.update(item["id"] for item in grouped)
            rendered = render_grouped_categories(data, grouped, lang, today)
        else:
            consumed.add(category["id"])
            rendered = render_category(data, category, lang, today)
        if rendered:
            chunks.append(rendered)
    return "\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n".join(chunks)


def ensure_template_placeholder(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "__CV_SECTIONS__" in text:
        return
    start = text.find(r"\section{__CV_RESEARCH__}")
    end = text.rfind(r"\end{document}")
    if start < 0 or end < 0:
        raise RuntimeError(f"Could not migrate CV template: {path.name}")
    text = text[:start] + "__CV_SECTIONS__\n%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%\n" + text[end:]
    path.write_text(text, encoding="utf-8")


def build(lang: str, today: date) -> Path:
    data = load_data()
    template = TEMPLATES[lang]
    ensure_template_placeholder(template)
    text = template.read_text(encoding="utf-8")
    text = text.replace("__CV_SECTIONS__", build_sections(data, lang, today))
    text = text.replace("__CV_LAST_UPDATED__", f"{today.year}/{today.month}/{today.day}")
    OUTPUTS[lang].write_text(str(core.strip_invisible_chars(text)), encoding="utf-8")
    return OUTPUTS[lang]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today")
    args = parser.parse_args()
    data = load_data()
    today = site_today(data, args.today)
    for lang in ("en", "zh"):
        print(f"Generated {build(lang, today).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
