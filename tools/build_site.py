#!/usr/bin/env python3
"""Generate all bilingual website sections from managed pages and categories."""
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

import process_request as core
from category_config import categories_for_page, items_for_category, migrate_category_data, normalized_pages
from homepage_config import homepage_activities, homepage_publications
from markup_config import rich_html as safe_rich_html
from site_settings_config import current_site_settings
from people_config import link_author_html, link_people_html, load_people

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
PAGE_FILES = [ROOT / p for p in ("index.html", "cv.html", "publications.html", "activities.html", "teaching.html", "zh/index.html", "zh/cv.html", "zh/publications.html", "zh/activities.html", "zh/teaching.html")]
PEOPLE = load_people()


def load_data() -> dict[str, Any]:
    return migrate_category_data(core.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8"))))


def esc(value: Any) -> str:
    return html.escape(str(core.strip_invisible_chars(str(value or ""))), quote=True)


def rich_html(value: Any) -> str:
    """Render the site's safe, dependency-free inline markup."""
    return safe_rich_html(core.strip_invisible_chars(str(value or "")))


def plain_value(entry: dict[str, Any], field: str, lang: str) -> str:
    value = entry.get(field)
    if isinstance(value, dict):
        return str(core.strip_invisible_chars(str(value.get(lang) or value.get("en") or value.get("zh") or "")))
    return str(core.strip_invisible_chars(str(value or "")))


def inline_value(entry: dict[str, Any], field: str, lang: str) -> str:
    rich = entry.get(f"{field}_html")
    if isinstance(rich, dict) and rich.get(lang):
        return str(rich[lang])
    return rich_html(plain_value(entry, field, lang))


def display_date(value: str) -> str:
    if not value:
        return ""
    try:
        d = date.fromisoformat(value)
        return f"{d.year}/{d.month}/{d.day}"
    except ValueError:
        return value


def display_range(entry: dict[str, Any]) -> str:
    if entry.get("date_label"):
        return ""
    start = str(entry.get("start_date") or "")
    end = str(entry.get("end_date") or start)
    if not start:
        return str(entry.get("year") or "")
    if not end or end == start:
        return display_date(start)
    return f"{display_date(start)}–{display_date(end)}"


def linked_title(entry: dict[str, Any], lang: str, field: str = "title") -> str:
    title = inline_value(entry, field, lang)
    url = str(entry.get("url") or "").strip()
    if url and title:
        return f'<a href="{esc(url)}" rel="noopener" target="_blank">{title}</a>'
    return title


def role_badge(entry: dict[str, Any], lang: str) -> str:
    role = plain_value(entry, "role", lang).strip()
    if not role or role.casefold() == "participant" or role == "一般參與者":
        return ""
    label = "身分" if lang == "zh" else "Role"
    return f'<p class="activity-role"><span>{label}</span>{rich_html(role)}</p>'


def render_activity(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    badge = role_badge(entry, lang) if entry.get("type") == "conference" else ""
    slides = ""
    if entry.get("slides_url"):
        label = "投影片" if lang == "zh" else "Slides"
        slides = (
            f'<div class="item-links"><a class="activity-link" '
            f'href="{esc(entry["slides_url"])}" rel="noopener" target="_blank">{label}</a></div>'
        )
    desc = inline_value(entry, "description", lang)
    return (
        f'<article class="timeline-item" data-entry-id="{esc(entry.get("id"))}">'
        f'<time>{esc(display_range(entry))}</time><div><h3>{title}</h3>{badge}'
        f'{f"<p>{desc}</p>" if desc else ""}{slides}</div></article>'
    )


def render_organization(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    kind = inline_value(entry, "organization_kind", lang)
    role = inline_value(entry, "role", lang)
    meta = "".join(f'<span class="organization-badge">{x}</span>' for x in (kind, role) if x)
    desc = inline_value(entry, "description", lang)
    return (
        f'<article class="timeline-item organization-item" data-entry-id="{esc(entry.get("id"))}">'
        f'<time>{esc(display_range(entry))}</time><div><div class="organization-meta">{meta}</div>'
        f'<h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</div></article>'
    )


def render_honor(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    org = inline_value(entry, "organization", lang)
    return f'<article class="timeline-item" data-entry-id="{esc(entry.get("id"))}"><time>{esc(entry.get("year"))}</time><div><h3>{title}</h3>{f"<p>{org}</p>" if org else ""}</div></article>'



def _split_english_authors(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [
        item.strip()
        for item in re.sub(r"\s*,?\s+and\s+", ", ", text, flags=re.I).split(",")
        if item.strip()
    ]


def _bibtex_key(entry: dict[str, Any]) -> str:
    authors = _split_english_authors(plain_value(entry, "authors", "en"))
    surname = re.sub(r"[^A-Za-z0-9]+", "", (authors[-1] if authors else "tsui").split()[-1]).lower() or "tsui"
    year = str(entry.get("year") or str(entry.get("date") or "")[:4] or "nd")
    words = re.findall(r"[A-Za-z0-9]+", plain_value(entry, "title", "en"))
    stop = {"a", "an", "and", "of", "on", "the", "in", "for", "to", "with"}
    keyword = next((word.lower() for word in words if word.lower() not in stop), "work")
    return f"{surname}{year}{keyword}"


def _bibtex_escape(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\\", r"\textbackslash{}")


def publication_bibtex(entry: dict[str, Any]) -> str:
    manual = str(entry.get("bibtex") or "").strip()
    if manual:
        return manual
    authors = " and ".join(_split_english_authors(plain_value(entry, "authors", "en")))
    title = plain_value(entry, "title", "en")
    year = str(entry.get("year") or str(entry.get("date") or "")[:4] or "")
    arxiv = str(entry.get("arxiv") or "").strip()
    doi_url = str(entry.get("doi_url") or "").strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi_url, flags=re.I) if doi_url else ""
    venue = plain_value(entry, "venue", "en")
    journal_like = bool(doi or entry.get("journal_url") or entry.get("group_id") == "journal-articles")
    entry_type = "article" if journal_like else "misc"
    fields: list[tuple[str, str]] = [("author", authors), ("title", title), ("year", year)]
    if journal_like and venue and not venue.lower().startswith("arxiv"):
        fields.append(("journal", venue))
    if doi:
        fields.append(("doi", doi))
    if arxiv:
        fields.extend((("eprint", arxiv), ("archivePrefix", "arXiv")))
    url = str(entry.get("journal_url") or entry.get("arxiv_url") or entry.get("pdf_url") or "").strip()
    if url:
        fields.append(("url", url))
    rows = [f"  {name} = {{{_bibtex_escape(value)}}}" for name, value in fields if value]
    return f"@{entry_type}{{{_bibtex_key(entry)},\n" + ",\n".join(rows) + "\n}"


def _latex_citation_escape(value: Any, *, strip: bool = True) -> str:
    text = str(value or "")
    if strip:
        text = text.strip()
    replacements = {
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
    return "".join(replacements.get(char, char) for char in text)


def _publication_title_latex(entry: dict[str, Any]) -> str:
    rich = (entry.get("title_html") or {}).get("en") if isinstance(entry.get("title_html"), dict) else ""
    raw = str(rich or plain_value(entry, "title", "en"))
    result: list[str] = []
    position = 0
    for match in re.finditer(r"<em>(.*?)</em>", raw, flags=re.I | re.S):
        before = re.sub(r"<[^>]+>", "", raw[position:match.start()])
        result.append(_latex_citation_escape(html.unescape(before), strip=False))
        inner = re.sub(r"<[^>]+>", "", match.group(1))
        result.append(f"${_latex_citation_escape(html.unescape(inner), strip=False)}$")
        position = match.end()
    tail = re.sub(r"<[^>]+>", "", raw[position:])
    result.append(_latex_citation_escape(html.unescape(tail), strip=False))
    return "".join(result).strip()


def publication_bibitem(entry: dict[str, Any]) -> str:
    manual = str(entry.get("bibitem") or "").strip()
    if manual:
        return manual
    authors = _latex_citation_escape(plain_value(entry, "authors", "en"))
    title = _publication_title_latex(entry)
    venue = _latex_citation_escape(plain_value(entry, "venue", "en"))
    year = str(entry.get("year") or str(entry.get("date") or "")[:4] or "").strip()
    arxiv = _latex_citation_escape(str(entry.get("arxiv") or "").strip())
    doi_url = str(entry.get("doi_url") or "").strip()
    doi = _latex_citation_escape(re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi_url, flags=re.I)) if doi_url else ""

    details: list[str] = []
    if venue:
        details.append(venue.rstrip(". "))
    if arxiv and arxiv.casefold() not in venue.casefold():
        details.append(f"arXiv:{arxiv}")
    if doi:
        details.append(f"doi:{doi}")
    if year and year not in venue:
        details.append(f"({year})")

    citation = ", ".join(part for part in (authors, rf"\emph{{{title}}}" if title else "", *details) if part)
    if citation and not citation.endswith("."):
        citation += "."
    return rf"\bibitem{{{_bibtex_key(entry)}}} {citation}".rstrip()


def bibtex_controls(entry: dict[str, Any], lang: str) -> str:
    bibtex = publication_bibtex(entry)
    bibitem = publication_bibitem(entry)
    if not bibtex and not bibitem:
        return ""
    identifier = "bibtex-" + re.sub(r"[^A-Za-z0-9_-]+", "-", str(entry.get("id") or "publication"))
    bibtex_id = f"{identifier}-bibtex"
    bibitem_id = f"{identifier}-bibitem"
    copied_label = "已複製" if lang == "zh" else "Copied"
    copy_bibtex = "複製 BibTeX" if lang == "zh" else "Copy BibTeX"
    copy_bibitem = r"複製 \bibitem" if lang == "zh" else r"Copy \bibitem"
    return (
        f'<button class="pub-bibtex-toggle" type="button" data-bibtex-toggle="{esc(identifier)}" '
        f'aria-expanded="false">BibTeX</button>'
        f'<div class="bibtex-panel" id="{esc(identifier)}" hidden>'
        f'<div class="citation-format-tabs" role="tablist" aria-label="Citation format">'
        f'<button type="button" class="citation-format-tab active" role="tab" aria-selected="true" '
        f'data-citation-panel="{esc(identifier)}" data-citation-format="bibtex">BibTeX</button>'
        f'<button type="button" class="citation-format-tab" role="tab" aria-selected="false" '
        f'data-citation-panel="{esc(identifier)}" data-citation-format="bibitem">\\bibitem</button></div>'
        f'<section class="citation-format-view" data-citation-view="bibtex" id="{esc(bibtex_id)}">'
        f'<div class="bibtex-panel-actions"><button type="button" class="bibtex-copy" '
        f'data-copy-citation="{esc(bibtex_id)}" data-copy-bibtex="{esc(bibtex_id)}" '
        f'data-copied-label="{esc(copied_label)}">{copy_bibtex}</button></div>'
        f'<pre><code>{esc(bibtex)}</code></pre></section>'
        f'<section class="citation-format-view" data-citation-view="bibitem" id="{esc(bibitem_id)}" hidden>'
        f'<div class="bibtex-panel-actions"><button type="button" class="bibtex-copy" '
        f'data-copy-citation="{esc(bibitem_id)}" data-copied-label="{esc(copied_label)}">{copy_bibitem}</button></div>'
        f'<pre><code>{esc(bibitem)}</code></pre></section></div>'
    )

def render_publication_article(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    links_html = "".join(
        f'<a href="{esc(link.get("url", ""))}" rel="noopener" target="_blank">{esc((link.get("label") or {}).get(lang) or (link.get("label") or {}).get("en") or "Link")}</a>'
        for link in entry.get("links", []) if link.get("url")
    )
    bibtex = bibtex_controls(entry, lang)
    links = f'<div class="pub-links">{links_html}{bibtex}</div>' if links_html or bibtex else ""
    title = (entry.get("homepage_title_html", {}) or {}).get(lang) if homepage else ""
    authors = (entry.get("homepage_authors_html", {}) or {}).get(lang) if homepage else ""
    title = title or inline_value(entry, "title", lang)
    authors = authors or inline_value(entry, "authors", lang)
    authors = link_author_html(authors, PEOPLE, lang)
    venue = inline_value(entry, "venue", lang)
    return (
        f'<article class="publication" data-entry-id="{esc(entry.get("id"))}"><div class="pub-year">{esc(entry.get("year"))}</div><div>'
        f'<h3>{title}</h3><p class="authors">{authors}</p><p class="venue">{venue}</p>{links}</div></article>'
    )


def page_href(data: dict[str, Any], page_id: str, lang: str) -> str:
    page = next((p for p in normalized_pages(data) if p["id"] == page_id), None)
    if not page:
        return ""
    target_lang = lang if page["path"].get(lang) else ("zh" if page["path"].get("zh") else "en")
    path = str(page["path"].get(target_lang) or "")
    if not path:
        return ""
    if lang == "zh":
        return Path(path).name if target_lang == "zh" else f"../{path}"
    return path


def _counterpart_href(page: dict[str, Any], lang: str) -> str:
    target_lang = "zh" if lang == "en" else "en"
    path = str((page.get("path") or {}).get(target_lang) or "")
    if not path:
        return ""
    return path if lang == "en" else f"../{path}"


def render_site_navigation(data: dict[str, Any], current_page_id: str, lang: str) -> str:
    pages = normalized_pages(data)
    links: list[str] = []
    for page in pages:
        if page.get("show_in_navigation", True) is False:
            continue
        if not str((page.get("path") or {}).get(lang) or ""):
            continue
        href = page_href(data, str(page.get("id") or ""), lang)
        if not href:
            continue
        label = str((page.get("name") or {}).get(lang) or page.get("id") or "")
        active = str(page.get("id") or "") == current_page_id
        attrs = ' class="active" aria-current="page"' if active else ""
        links.append(
            f'<a{attrs} data-nav="{esc(page.get("id"))}" href="{esc(href)}">{esc(label)}</a>'
        )

    home_href = page_href(data, "home", lang)
    if home_href:
        contact_label = "聯絡" if lang == "zh" else "Contact"
        links.append(f'<a data-nav="contact" href="{esc(home_href)}#contact">{contact_label}</a>')

    current = next((page for page in pages if page.get("id") == current_page_id), None)
    counterpart = _counterpart_href(current, lang) if current else ""
    if counterpart:
        label = "中文" if lang == "en" else "English"
        aria = "切換至中文版" if lang == "en" else "Switch to English"
        links.append(
            f'<a aria-label="{aria}" class="language-toggle" href="{esc(counterpart)}">{label}</a>'
        )
    return '<nav aria-label="Primary navigation" class="site-nav" id="site-nav">' + "".join(links) + "</nav>"


def replace_navigation(text: str, data: dict[str, Any], current_page_id: str, lang: str) -> str:
    navigation = render_site_navigation(data, current_page_id, lang)
    updated, count = re.subn(
        r'<nav\b(?=[^>]*\bclass="[^"]*\bsite-nav\b[^"]*")[^>]*>.*?</nav>',
        lambda _: navigation,
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError("Could not replace site navigation")
    return updated


def render_teaching(data: dict[str, Any], entry: dict[str, Any], lang: str) -> str:
    term = rich_html(plain_value(entry, "term", lang))
    course = rich_html(plain_value(entry, "course", lang))
    role = rich_html(plain_value(entry, "role", lang))
    links: list[str] = []
    course_page = str(entry.get("course_page_id") or "")
    href = page_href(data, course_page, lang) if course_page else ""
    if href:
        label = "課程資訊" if lang == "zh" else "Course Information"
        links.append(f'<a href="{esc(href)}">{label}</a>')
    notes_url = str(entry.get("lecture_notes_url") or "").strip()
    if notes_url:
        notes_title = plain_value(entry, "lecture_notes_title", lang) or ("講義" if lang == "zh" else "Lecture Notes")
        links.append(f'<a href="{esc(notes_url)}" rel="noopener" target="_blank">{esc(notes_title)}</a>')
    links_html = f'<div class="item-links">{"".join(links)}</div>' if links else ""
    return f'<article class="teaching-card" data-entry-id="{esc(entry.get("id"))}"><div class="date">{term}</div><div><h3>{course}</h3>{f"<p class=\"venue\">{role}</p>" if role else ""}{links_html}</div></article>'


def render_interest(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    desc = rich_html(plain_value(entry, "description", lang))
    return f'<article class="interest-summary-item" data-entry-id="{esc(entry.get("id"))}"><h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</article>'


def render_education(entry: dict[str, Any], lang: str) -> str:
    when = plain_value(entry, "date_label", lang) or display_range(entry)
    title = linked_title(entry, lang)
    org = rich_html(plain_value(entry, "organization", lang))
    desc = rich_html(plain_value(entry, "description", lang))
    detail = " · ".join(x for x in (org, desc) if x)
    return f'<article data-entry-id="{esc(entry.get("id"))}"><time>{esc(when)}</time><div><h3>{title}</h3>{f"<p>{detail}</p>" if detail else ""}</div></article>'


def render_generic(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    desc = rich_html(plain_value(entry, "description", lang))
    when = plain_value(entry, "date_label", lang) or display_range(entry)
    return f'<article class="timeline-item" data-entry-id="{esc(entry.get("id"))}"><time>{esc(when)}</time><div><h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</div></article>'


def render_contact(items: list[dict[str, Any]], lang: str) -> str:
    cards = []
    for entry in items:
        title = rich_html(plain_value(entry, "title", lang))
        value = rich_html(plain_value(entry, "description", lang))
        url = str(entry.get("url") or "").strip()
        body = f'<a href="{esc(url)}" rel="noopener">{value}</a>' if url else f'<p>{value}</p>'
        cards.append(f'<div data-entry-id="{esc(entry.get("id"))}"><span>{title}</span>{body}</div>')
    return '<div class="contact-grid">' + "".join(cards) + '</div>'


def category_items(data: dict[str, Any], category: dict[str, Any], today: date) -> list[dict[str, Any]]:
    kind = category["kind"]
    if kind == "featured_publications":
        return homepage_publications(data)
    if kind == "upcoming":
        return homepage_activities(data, today)
    return items_for_category(data, category["id"])


def category_body(data: dict[str, Any], category: dict[str, Any], lang: str, today: date) -> tuple[str, int]:
    kind = category["kind"]
    items = category_items(data, category, today)
    if kind == "featured_publications":
        return '<ol class="publication-list">' + "".join(f'<li>{render_publication_article(x, lang, homepage=True)}</li>' for x in items) + '</ol>', len(items)
    if kind == "upcoming":
        return '<div class="timeline">' + "".join(render_activity(x, lang) for x in items) + '</div>', len(items)
    if kind == "contact":
        return render_contact(items, lang), len(items)
    if kind == "interest":
        return '<div class="interest-summary">' + "".join(render_interest(x, lang) for x in items) + '</div>', len(items)
    if kind == "education":
        return '<div class="compact-list">' + "".join(render_education(x, lang) for x in items) + '</div>', len(items)
    if kind == "honor":
        return '<div class="timeline compact-timeline">' + "".join(render_honor(x, lang) for x in items) + '</div>', len(items)
    if kind == "publication":
        return '<ol class="publication-list">' + "".join(f'<li>{render_publication_article(x, lang)}</li>' for x in items) + '</ol>', len(items)
    if kind in {"visit", "talk", "conference"}:
        return '<div class="timeline compact-timeline">' + "".join(render_activity(x, lang) for x in items) + '</div>', len(items)
    if kind == "organization":
        return '<div class="timeline organization-timeline">' + "".join(render_organization(x, lang) for x in items) + '</div>', len(items)
    if kind == "teaching":
        return '<div class="teaching-grid">' + "".join(render_teaching(data, x, lang) for x in items) + '</div>', len(items)
    if kind == "personal":
        return render_contact(items, lang), len(items)
    return '<div class="timeline">' + "".join(render_generic(x, lang) for x in items) + '</div>', len(items)


def render_category(data: dict[str, Any], category: dict[str, Any], lang: str, today: date, index: int) -> str:
    body, count = category_body(data, category, lang, today)
    if count == 0 and category["kind"] not in {"contact"}:
        return ""
    label = rich_html(category.get("label", {}).get(lang, ""))
    title = rich_html(category.get("title", {}).get(lang, ""))
    intro = rich_html(category.get("intro", {}).get(lang, ""))
    cid = esc(category["id"])
    soft = " section-soft" if index % 2 == 0 else ""
    classes = f'section managed-category category-{esc(category["kind"])}{soft}'
    if category["kind"] == "contact":
        classes += " contact-section"
    return (
        f'<section class="{classes}" data-category-id="{cid}" id="{cid}"><div class="container">'
        f'<p class="section-label">{label}</p><h2>{title}</h2>{f"<p class=\"section-intro\">{intro}</p>" if intro else ""}{body}</div></section>'
    )


def render_home_overview_panel(
    data: dict[str, Any],
    category: dict[str, Any],
    lang: str,
    today: date,
) -> str:
    """Render the two legacy homepage columns from managed category data."""
    items = category_items(data, category, today)
    label = rich_html(category.get("label", {}).get(lang, ""))
    title = rich_html(category.get("title", {}).get(lang, ""))
    intro = rich_html(category.get("intro", {}).get(lang, ""))
    cid = esc(category["id"])
    intro_html = f'<p class="section-intro">{intro}</p>' if intro else ""
    if category["kind"] == "featured_publications":
        entries = "".join(f"<li>{render_publication_article(item, lang, homepage=True)}</li>" for item in items)
        link_text = "所有論文 →" if lang == "zh" else "All publications →"
        return (
            f'<div class="home-publications managed-category category-featured_publications" '
            f'data-category-id="{cid}" id="{cid}"><div class="home-section-head"><div>'
            f'<p class="section-label">{label}</p><h2>{title}</h2></div>'
            f'<a class="text-link" href="publications.html">{link_text}</a></div>{intro_html}'
            f'<ol class="publication-list" id="latest-publications">\n'
            f'<!-- CMS:HOME_PUBLICATIONS:START -->\n{entries}\n'
            f'<!-- CMS:HOME_PUBLICATIONS:END -->\n</ol></div>'
        )
    entries = "".join(render_activity(item, lang) for item in items)
    link_text = "所有活動 →" if lang == "zh" else "All activities →"
    return (
        f'<aside class="home-upcoming managed-category category-upcoming" '
        f'data-category-id="{cid}" id="{cid}"><p class="section-label">{label}</p>'
        f'<h2>{title}</h2>{intro_html}<div class="timeline">\n'
        f'<!-- CMS:UPCOMING:START -->\n{entries}\n'
        f'<!-- CMS:UPCOMING:END -->\n</div>'
        f'<a class="text-link" href="activities.html">{link_text}</a></aside>'
    )


def render_home_contact(
    data: dict[str, Any],
    category: dict[str, Any],
    lang: str,
    today: date,
) -> str:
    """Keep the original split contact layout and its public #contact anchor."""
    items = category_items(data, category, today)
    label = rich_html(category.get("label", {}).get(lang, ""))
    title = rich_html(category.get("title", {}).get(lang, ""))
    intro = rich_html(category.get("intro", {}).get(lang, ""))
    cid = esc(category["id"])
    intro_html = f'<p class="section-intro">{intro}</p>' if intro else ""
    return (
        f'<section class="section managed-category category-contact contact-section" '
        f'data-category-id="{cid}" id="contact"><div class="container split"><div>'
        f'<p class="section-label">{label}</p><h2>{title}</h2>{intro_html}</div>'
        f'{render_contact(items, lang)}</div></section>'
    )


def render_home_sections(
    data: dict[str, Any],
    categories: list[dict[str, Any]],
    lang: str,
    today: date,
) -> str:
    """Restore the legacy homepage composition while retaining managed categories."""
    overview_categories = [
        category
        for category in categories
        if category["kind"] in {"featured_publications", "upcoming"}
    ]
    overview_panels = [
        panel
        for category in sorted(
            overview_categories,
            key=lambda c: 0 if c["kind"] == "featured_publications" else 1,
        )
        if (panel := render_home_overview_panel(data, category, lang, today))
    ]
    overview = ""
    if overview_panels:
        single = " home-overview-single" if len(overview_panels) == 1 else ""
        overview = (
            f'<section class="home-overview"><div class="container home-overview-grid{single}">'
            f'{"".join(overview_panels)}</div></section>'
        )

    first_overview_index = min(
        (index for index, category in enumerate(categories) if category in overview_categories),
        default=0,
    )
    rendered: list[str] = []
    section_index = 0
    for index, category in enumerate(categories):
        if index == first_overview_index and overview:
            rendered.append(overview)
            section_index += 1
        if category in overview_categories:
            continue
        if category["kind"] == "contact":
            rendered.append(render_home_contact(data, category, lang, today))
        else:
            section = render_category(data, category, lang, today, section_index)
            if section:
                rendered.append(section)
        section_index += 1
    if overview and first_overview_index >= len(categories):
        rendered.append(overview)
    return "".join(rendered)


def page_header(data: dict[str, Any], page_id: str, lang: str) -> str:
    page = next(p for p in normalized_pages(data) if p["id"] == page_id)
    header = page.get("header")
    if not header:
        return ""
    label = rich_html(header["label"][lang])
    title = rich_html(header["title"][lang])
    intro = rich_html(header["intro"][lang])
    download = ""
    if page_id == "cv":
        href = "https://hctsui.github.io/files/Hung-Chun-Tsui-CV-zh.pdf" if lang == "zh" else "https://hctsui.github.io/files/Hung-Chun-Tsui-CV.pdf"
        text = "下載 PDF 履歷" if lang == "zh" else "Download PDF CV"
        download = f'<a class="button primary cv-download" href="{href}" rel="noopener" target="_blank">{text}</a>'
    return f'<section class="page-hero"><div class="container"><p class="section-label">{label}</p><h1 class="page-title">{title}</h1><p class="page-intro">{intro}</p>{download}</div></section>'


def extract_home_hero(text: str) -> str:
    match = re.search(r'(<section class="home-hero".*?</section>)', text, flags=re.S)
    if not match:
        raise RuntimeError("Could not find home hero")
    return match.group(1)


def replace_main(text: str, content: str) -> str:
    replacement = f'<main id="main">{content}</main>'
    updated, count = re.subn(r'<main id="main">.*?</main>', lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not replace main element")
    return updated


def update_page_title(text: str, title: str) -> str:
    replacement = f'<title>{esc(title)}</title>'
    updated, count = re.subn(r'<title>.*?</title>', lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not update title")
    return updated


def _absolute_url(base_url: str, value: str, page_path: str = "") -> str:
    from urllib.parse import urljoin

    base = base_url.rstrip("/") + "/"
    if not value:
        return urljoin(base, page_path)
    if re.match(r"^https?://", value, flags=re.I):
        return value
    return urljoin(base, value.lstrip("/"))


def _replace_or_insert_head(text: str, pattern: str, replacement: str) -> str:
    if re.search(pattern, text, flags=re.I | re.S):
        return re.sub(pattern, lambda _: replacement, text, count=1, flags=re.I | re.S)
    return text.replace("</head>", replacement + "\n</head>", 1)


def apply_seo_metadata(text: str, data: dict[str, Any], page: dict[str, Any], lang: str) -> str:
    settings = current_site_settings(data)["seo"]
    page_id = str(page.get("id") or "home")
    page_settings = settings["pages"].get(page_id) or settings["pages"]["home"]
    title = page_settings["title"][lang]
    description = page_settings["description"][lang]
    og_title = page_settings["og_title"][lang] or title
    og_description = page_settings["og_description"][lang] or description
    rel_path = str((page.get("path") or {}).get(lang) or "")
    canonical_path = rel_path[:-10] if rel_path.endswith("index.html") else rel_path
    canonical = _absolute_url(settings["base_url"], "", canonical_path)
    image = _absolute_url(settings["base_url"], page_settings.get("og_image") or settings["default_image"])
    site_name = settings["site_name"][lang]
    counterpart_lang = "zh" if lang == "en" else "en"
    counterpart_path = str((page.get("path") or {}).get(counterpart_lang) or "")
    if counterpart_path.endswith("index.html"):
        counterpart_path = counterpart_path[:-10]
    counterpart = _absolute_url(settings["base_url"], "", counterpart_path) if counterpart_path or page_id == "home" else ""

    text = update_page_title(text, title)
    tags = [
        f'<meta name="description" content="{esc(description)}">',
        f'<link rel="canonical" href="{esc(canonical)}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{esc(og_title)}">',
        f'<meta property="og:description" content="{esc(og_description)}">',
        f'<meta property="og:url" content="{esc(canonical)}">',
        f'<meta property="og:image" content="{esc(image)}">',
        f'<meta property="og:site_name" content="{esc(site_name)}">',
        f'<meta property="og:locale" content="{"zh_TW" if lang == "zh" else "en_US"}">',
        f'<meta property="og:locale:alternate" content="{"en_US" if lang == "zh" else "zh_TW"}">',
        f'<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{esc(og_title)}">',
        f'<meta name="twitter:description" content="{esc(og_description)}">',
        f'<meta name="twitter:image" content="{esc(image)}">',
        f'<link rel="alternate" hreflang="{lang}" href="{esc(canonical)}">',
    ]
    if counterpart:
        tags.append(f'<link rel="alternate" hreflang="{counterpart_lang}" href="{esc(counterpart)}">')
    default_path = str((page.get("path") or {}).get("en") or rel_path)
    if default_path.endswith("index.html"):
        default_path = default_path[:-10]
    tags.append(f'<link rel="alternate" hreflang="x-default" href="{esc(_absolute_url(settings["base_url"], "", default_path))}">')
    block = "\n".join(tags)
    # Remove all metadata managed by this function before inserting the fresh block.
    managed_patterns = [
        r'<meta\b(?=[^>]*\bname=["\']description["\'])[^>]*>\s*',
        r'<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>\s*',
        r'<meta\b(?=[^>]*\bproperty=["\']og:[^"\']+["\'])[^>]*>\s*',
        r'<meta\b(?=[^>]*\bname=["\']twitter:[^"\']+["\'])[^>]*>\s*',
        r'<link\b(?=[^>]*\brel=["\']alternate["\'])[^>]*>\s*',
    ]
    for pattern in managed_patterns:
        text = re.sub(pattern, "", text, flags=re.I)
    return text.replace("</head>", block + "\n</head>", 1)


_ANALYTICS_START = "<!-- managed:cloudflare-web-analytics -->"
_ANALYTICS_END = "<!-- /managed:cloudflare-web-analytics -->"


def apply_cloudflare_analytics(text: str, data: dict[str, Any]) -> str:
    """Insert the Cloudflare beacon only in generated public pages."""
    pattern = re.escape(_ANALYTICS_START) + r".*?" + re.escape(_ANALYTICS_END) + r"\s*"
    text = re.sub(pattern, "", text, flags=re.S)
    analytics = current_site_settings(data)["analytics"]
    if not analytics.get("enabled") or not analytics.get("token"):
        return text
    payload = json.dumps({"token": analytics["token"]}, separators=(",", ":"))
    block = (
        f"{_ANALYTICS_START}\n"
        '<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" '
        f"data-cf-beacon='{esc(payload)}'></script>\n"
        f"{_ANALYTICS_END}"
    )
    return text.replace("</body>", block + "\n</body>", 1)


_FOOTER_ICONS = {
    "copyright": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M15 9.5a4 4 0 1 0 0 5"></path></svg>',
    "email": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="m4 7 8 6 8-6"></path></svg>',
    "link": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"></path><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"></path></svg>',
    "github": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 0 0-2.8 17.6c.5.1.7-.2.7-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 0 1.6 1.1 1.6 1.1.9 1.6 2.4 1.1 2.9.8.1-.7.4-1.1.7-1.3-2.2-.3-4.6-1.1-4.6-5A3.9 3.9 0 0 1 7.2 8c-.1-.3-.5-1.3.1-2.7 0 0 .9-.3 2.8 1.1a9.7 9.7 0 0 1 5.1 0c2-1.4 2.8-1.1 2.8-1.1.6 1.4.2 2.4.1 2.7a3.9 3.9 0 0 1 1 2.7c0 3.9-2.4 4.7-4.6 5 .4.3.7.9.7 1.8v2.6c0 .3.2.6.7.5A9 9 0 0 0 12 3Z"></path></svg>',
    "orcid": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="8.5" cy="8" r="1"></circle><path d="M8.5 11v5M11.5 11v5M11.5 11h2a2.5 2.5 0 0 1 0 5h-2"></path></svg>',
    "location": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>',
    "book": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22Z"></path><path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22Z"></path></svg>',
    "calendar": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M7 3v4M17 3v4M3 10h18"></path></svg>',
}


def _footer_icon(name: str, custom_icon: str = "") -> str:
    if name == "other" and custom_icon:
        return f'<img class="footer-custom-icon" src="{esc(custom_icon)}" alt="">'
    return _FOOTER_ICONS.get(name, "")


def _existing_updated(text: str, lang: str, today: date) -> str:
    pattern = r'最後更新：(\d{4}/\d{1,2}/\d{1,2})' if lang == "zh" else r'Last updated:\s*(\d{4}/\d{1,2}/\d{1,2})'
    match = re.search(pattern, text)
    return match.group(1) if match else f"{today.year}/{today.month}/{today.day}"


def render_footer(data: dict[str, Any], lang: str, today: date, *, updated: str | None = None) -> str:
    settings = current_site_settings(data)
    footer = settings["footer"]
    base_url = settings["seo"]["base_url"]
    values = {"year": str(today.year), "updated": updated or f"{today.year}/{today.month}/{today.day}"}
    zones: dict[str, list[str]] = {"left": [], "center": [], "right": []}
    for item in footer["items"]:
        text = item["text"].get(lang) or item["text"].get("en") or item["text"].get("zh") or ""
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        custom_icon = str(item.get("custom_icon") or "").strip()
        if custom_icon and not re.match(r"^https?://", custom_icon, flags=re.I):
            custom_icon = _absolute_url(base_url, custom_icon)
        content = f'{_footer_icon(item["icon"], custom_icon)}<span>{esc(text)}</span>'
        url = str(item.get("url") or "").strip()
        if url and not re.match(r"^(?:https?://|mailto:)", url, flags=re.I):
            url = _absolute_url(base_url, url)
        if url:
            attrs = ' rel="noopener"' + (' target="_blank"' if item.get("new_tab") else "")
            content = f'<a class="footer-item" href="{esc(url)}"{attrs}>{content}</a>'
        else:
            content = f'<span class="footer-item">{content}</span>'
        zones[item["alignment"]].append(content)
    inner = "".join(
        f'<div class="footer-zone footer-{name}">{"".join(zones[name])}</div>'
        for name in ("left", "center", "right")
    )
    return f'<footer class="site-footer"><div class="container footer-inner">{inner}</div></footer>'


def replace_footer(text: str, footer: str) -> str:
    updated, count = re.subn(r'<footer class="site-footer">.*?</footer>', lambda _: footer, text, count=1, flags=re.S)
    if count != 1:
        updated = text.replace("</body>", footer + "\n</body>", 1)
    return updated

def custom_page_shell(page: dict[str, Any], lang: str) -> str:
    template = ROOT / ("zh/teaching.html" if lang == "zh" else "teaching.html")
    text = template.read_text(encoding="utf-8")
    text = re.sub(r'class="active"\s+', "", text)
    text = re.sub(r'<body data-page="[^"]+"', f'<body data-page="{esc(page["id"])}"', text, count=1)
    counterpart = page["path"].get("en" if lang == "zh" else "zh")
    if counterpart:
        href = f"../{counterpart}" if lang == "zh" else counterpart
        text = re.sub(r'(<a[^>]+class="language-toggle"[^>]+href=")[^"]+(")', rf'\g<1>{esc(href)}\2', text, count=1)
    else:
        text = re.sub(r'<a[^>]+class="language-toggle"[^>]*>.*?</a>', "", text, count=1, flags=re.S)
    return text


def page_theme_style(color: str) -> str:
    value = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color or "") else "#8b3d2e"
    rgb = tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    dark = "#" + "".join(f"{round(channel * .68):02x}" for channel in rgb)
    soft_rgb = tuple(round(255 - (255 - channel) * .22) for channel in rgb)
    soft = "#" + "".join(f"{channel:02x}" for channel in soft_rgb)
    return f"--accent:{value};--accent-dark:{dark};--accent-soft:{soft}"


def apply_page_theme(text: str, page: dict[str, Any]) -> str:
    style = page_theme_style(str(page.get("color") or ""))
    return re.sub(r'(<body\b[^>]*?)(?:\sstyle="[^"]*")?(>)', rf'\1 style="{style}"\2', text, count=1)


def _not_found_navigation(data: dict[str, Any], lang: str, base_url: str) -> str:
    links = []
    for page in normalized_pages(data):
        if page.get("show_in_navigation", True) is False:
            continue
        path = str((page.get("path") or {}).get(lang) or "")
        if not path:
            continue
        label = str((page.get("name") or {}).get(lang) or page.get("id") or "")
        links.append(f'<a href="{esc(_absolute_url(base_url, path))}">{esc(label)}</a>')
    home_path = next(
        (str((page.get("path") or {}).get(lang) or "") for page in normalized_pages(data) if page.get("id") == "home"),
        "",
    )
    if home_path:
        contact_label = "聯絡" if lang == "zh" else "Contact"
        links.append(f'<a href="{esc(_absolute_url(base_url, home_path))}#contact">{contact_label}</a>')
    return '<nav class="not-found-nav" aria-label="Website navigation">' + "".join(links) + "</nav>"


def render_404_page(data: dict[str, Any], today: date) -> str:
    settings = current_site_settings(data)
    error = settings["error_page"]
    seo = settings["seo"]
    base = seo["base_url"]
    colors = error["colors"]
    home = {
        "en": _absolute_url(base, "index.html"),
        "zh": _absolute_url(base, "zh/index.html"),
    }
    secondary = {
        lang: _absolute_url(base, error["secondary_url"][lang])
        for lang in ("en", "zh")
    }
    css_url = _absolute_url(base, "assets/style.css")
    language_payload = json.dumps(
        {"home": home, "redirect": error["auto_redirect"]},
        ensure_ascii=False, separators=(",", ":"),
    )

    def language_panel(lang: str) -> str:
        redirect_text = "Returning home in {seconds} seconds." if lang == "en" else "將在 {seconds} 秒後返回首頁。"
        redirect = ""
        if error["auto_redirect"]["enabled"]:
            redirect = (
                f'<p class="not-found-redirect" data-countdown-template="{esc(redirect_text)}" '
                f'data-countdown>{esc(redirect_text.format(seconds=error["auto_redirect"]["seconds"]))}</p>'
            )
        secondary_button = ""
        if error["secondary_label"][lang]:
            secondary_button = (
                f'<a class="not-found-button secondary" href="{esc(secondary[lang])}">'
                f'{esc(error["secondary_label"][lang])}</a>'
            )
        footer = render_footer(data, lang, today) if error["show_footer"] else ""
        nav = _not_found_navigation(data, lang, base) if error["show_navigation"] else ""
        switch_label = "中文" if lang == "en" else "English"
        return f'''<div class="not-found-language" data-language="{lang}" hidden>
          <header class="not-found-header">
            <a class="not-found-brand" href="{esc(home[lang])}">{esc(seo["site_name"][lang])}</a>
            {nav}
            <button class="not-found-language-button" type="button" data-switch-language>{switch_label}</button>
          </header>
          <main class="not-found-main">
            <section class="not-found-card">
              <div class="not-found-code">404</div>
              <p class="not-found-eyebrow">{esc(error["eyebrow"][lang])}</p>
              <h1>{esc(error["title"][lang])}</h1>
              <p class="not-found-description">{esc(error["description"][lang])}</p>
              {redirect}
              <div class="not-found-actions">
                <a class="not-found-button primary" href="{esc(home[lang])}">{esc(error["home_label"][lang])}</a>
                {secondary_button}
              </div>
            </section>
          </main>
          {footer}
        </div>'''

    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>404 | {esc(seo["site_name"]["en"])}</title>
  <link rel="stylesheet" href="{esc(css_url)}">
  <style>
    :root{{--nf-background:{colors["background"]};--nf-surface:{colors["surface"]};--nf-accent:{colors["accent"]};--nf-text:{colors["text"]};--nf-muted:{colors["muted"]};--nf-button:{colors["button"]};--nf-button-text:{colors["button_text"]}}}
    body{{margin:0;background:var(--nf-background);color:var(--nf-text)}}
    .not-found-language{{min-height:100vh;display:flex;flex-direction:column}}
    .not-found-header{{width:min(1120px,calc(100% - 32px));margin:auto;padding:24px 0;display:flex;align-items:center;gap:20px}}
    .not-found-brand{{font-family:Georgia,"Times New Roman",serif;font-size:1.2rem;font-weight:800;color:var(--nf-text);text-decoration:none}}
    .not-found-nav{{margin-left:auto;display:flex;gap:16px;flex-wrap:wrap}}.not-found-nav a{{color:var(--nf-muted);font-weight:700;text-decoration:none}}.not-found-nav a:hover{{color:var(--nf-accent)}}
    .not-found-language-button{{border:1px solid color-mix(in srgb,var(--nf-text) 20%,transparent);border-radius:999px;background:var(--nf-surface);color:var(--nf-text);padding:8px 12px;font:inherit;font-weight:800;cursor:pointer}}
    .not-found-main{{width:min(900px,calc(100% - 32px));margin:auto;flex:1;display:grid;place-items:center;padding:48px 0 72px}}
    .not-found-card{{width:100%;text-align:center;padding:clamp(36px,7vw,76px);border:1px solid color-mix(in srgb,var(--nf-text) 14%,transparent);border-radius:28px;background:var(--nf-surface);box-shadow:0 24px 60px color-mix(in srgb,var(--nf-text) 10%,transparent)}}
    .not-found-code{{font:800 clamp(4.5rem,16vw,9rem)/.85 Georgia,"Times New Roman",serif;color:color-mix(in srgb,var(--nf-accent) 18%,transparent)}}
    .not-found-eyebrow{{margin:1.3rem 0 .5rem;text-transform:uppercase;letter-spacing:.15em;color:var(--nf-accent);font-size:.78rem;font-weight:900}}
    .not-found-card h1{{margin:.25rem 0 1rem;color:var(--nf-text);font-size:clamp(2rem,6vw,4.2rem)}}
    .not-found-description{{max-width:680px;margin:0 auto;color:var(--nf-muted);font-size:1.08rem}}
    .not-found-redirect{{margin:1rem 0 0;color:var(--nf-accent);font-weight:800}}
    .not-found-actions{{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:28px}}
    .not-found-button{{display:inline-flex;padding:11px 17px;border-radius:999px;font-weight:850;text-decoration:none;border:1px solid var(--nf-button)}}
    .not-found-button.primary{{background:var(--nf-button);color:var(--nf-button-text)}}.not-found-button.secondary{{background:transparent;color:var(--nf-button)}}
    .not-found-language .site-footer{{margin-top:auto}}
    @media(max-width:760px){{.not-found-nav{{display:none}}.not-found-header{{justify-content:space-between}}}}
  </style>
</head>
<body data-page="404">
  {language_panel("en")}
  {language_panel("zh")}
  <script>
    (()=>{{
      const config={language_payload};
      let lang=location.pathname.startsWith('/zh/')||(!location.pathname.includes('/en/')&&navigator.language.toLowerCase().startsWith('zh'))?'zh':'en';
      let redirectTimer=null,countdownTimer=null;
      function show(next){{
        lang=next;document.documentElement.lang=lang;
        document.querySelectorAll('[data-language]').forEach(el=>el.hidden=el.dataset.language!==lang);
        if(redirectTimer)clearTimeout(redirectTimer);if(countdownTimer)clearInterval(countdownTimer);
        const counter=document.querySelector(`[data-language="${{lang}}"] [data-countdown]`);
        if(counter){{let remaining=config.redirect.seconds;const update=()=>counter.textContent=counter.dataset.countdownTemplate.replace('{{seconds}}',remaining);update();countdownTimer=setInterval(()=>{{remaining-=1;update();if(remaining<=0)clearInterval(countdownTimer)}},1000)}}
        if(config.redirect.enabled)redirectTimer=setTimeout(()=>location.href=config.home[lang],config.redirect.seconds*1000);
      }}
      document.addEventListener('click',event=>{{if(event.target.closest('[data-switch-language]'))show(lang==='en'?'zh':'en')}});
      show(lang);
    }})();
  </script>
</body>
</html>'''
    page = apply_cloudflare_analytics(page, data)
    return page


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    return datetime.now(ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))).date()


def build(today: date, update_date: bool = True) -> list[Path]:
    data = load_data()
    pages = {p["id"]: p for p in normalized_pages(data)}
    changed: list[Path] = []
    for page_id, page in pages.items():
        for lang in ("en", "zh"):
            rel = page["path"][lang]
            if not rel:
                continue
            path = ROOT / rel
            if path.exists():
                old = path.read_text(encoding="utf-8")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                old = custom_page_shell(page, lang)
            categories = categories_for_page(data, page_id)
            if page_id == "home":
                sections = render_home_sections(data, categories, lang, today)
                content = extract_home_hero(old) + sections
            else:
                rendered = [render_category(data, c, lang, today, i) for i, c in enumerate(categories)]
                sections = "".join(x for x in rendered if x)
                content = page_header(data, page_id, lang) + sections
            new = replace_main(old, content)
            new = replace_navigation(new, data, page_id, lang)
            new = apply_page_theme(new, page)
            new = apply_seo_metadata(new, data, page, lang)
            updated_value = f"{today.year}/{today.month}/{today.day}" if update_date else _existing_updated(old, lang, today)
            new = replace_footer(new, render_footer(data, lang, today, updated=updated_value))
            new = link_people_html(new, PEOPLE, lang)
            new = apply_cloudflare_analytics(new, data)
            if new != old:
                path.write_text(new, encoding="utf-8")
                changed.append(path)
    error_path = ROOT / "404.html"
    error_old = error_path.read_text(encoding="utf-8") if error_path.exists() else ""
    error_new = render_404_page(data, today)
    if error_new != error_old:
        error_path.write_text(error_new, encoding="utf-8")
        changed.append(error_path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--today")
    parser.add_argument("--no-update-date", action="store_true")
    args = parser.parse_args()
    data = load_data()
    changed = build(site_today(data, args.today), update_date=not args.no_update_date)
    for path in changed:
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
