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
PAGE_FILES = [ROOT / p for p in ("index.html", "cv.html", "publications.html", "activities.html", "teaching.html", "contact.html", "zh/index.html", "zh/cv.html", "zh/publications.html", "zh/activities.html", "zh/teaching.html", "zh/contact.html")]
PEOPLE = load_people()
INDEXABLE_PAGE_IDS = {"home", "cv", "publications", "activities", "teaching", "contact"}


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
        f'<article class="timeline-item" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}">'
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
        f'<article class="timeline-item organization-item" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}">'
        f'<time>{esc(display_range(entry))}</time><div><div class="organization-meta">{meta}</div>'
        f'<h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</div></article>'
    )


def render_honor(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    org = inline_value(entry, "organization", lang)
    return f'<article class="timeline-item" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><time>{esc(entry.get("year"))}</time><div><h3>{title}</h3>{f"<p>{org}</p>" if org else ""}</div></article>'



def _split_english_authors(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [
        item.strip()
        for item in re.sub(r"\s*,?\s+and\s+", ", ", text, flags=re.I).split(",")
        if item.strip()
    ]


def _author_surname_initial(author: str) -> str:
    """Return a stable Latin initial for one display-form author name."""
    text = re.sub(r"<[^>]+>", "", str(author or "")).strip()
    if not text:
        return ""
    # Support both ``Hung-Chun Tsui`` and ``Tsui, Hung-Chun``.
    surname = text.split(",", 1)[0].strip() if "," in text else text.split()[-1]
    match = re.search(r"[A-Za-z0-9]", surname)
    return match.group(0).upper() if match else ""


def _citation_key_base(entry: dict[str, Any]) -> str:
    authors = _split_english_authors(plain_value(entry, "authors", "en"))
    initials = "".join(filter(None, (_author_surname_initial(author) for author in authors))) or "T"
    year = re.sub(r"\D+", "", str(entry.get("year") or str(entry.get("date") or "")[:4] or ""))
    year_suffix = year[-2:] if year else "ND"
    return f"{initials}{year_suffix}"


def assign_citation_keys(data: dict[str, Any]) -> None:
    """Assign deterministic in-memory keys, adding a/b/c only for collisions."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in data.get("publications", []):
        groups.setdefault(_citation_key_base(entry), []).append(entry)
    for base, entries in groups.items():
        ordered = sorted(entries, key=lambda item: (str(item.get("date") or ""), str(item.get("id") or "")))
        if len(ordered) == 1:
            ordered[0]["_citation_key"] = base
            continue
        for index, entry in enumerate(ordered):
            # a-z is ample for a single author group/year; continue as a1, a2 if ever exceeded.
            suffix = chr(ord("a") + index) if index < 26 else f"a{index - 25}"
            entry["_citation_key"] = f"{base}{suffix}"


def _bibtex_key(entry: dict[str, Any]) -> str:
    return str(entry.get("_citation_key") or _citation_key_base(entry))


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
    # Field order mirrors the compact arXiv/BibTeX export style commonly used
    # in mathematics: title/author/year first, then arXiv metadata.
    fields: list[tuple[str, str]] = [("title", title), ("author", authors), ("year", year)]
    if journal_like and venue and not venue.lower().startswith("arxiv"):
        fields.append(("journal", venue))
    if arxiv:
        fields.extend((("eprint", arxiv), ("archivePrefix", "arXiv")))
        primary_class = str(entry.get("primary_category") or entry.get("primary_class") or "").strip()
        if primary_class:
            fields.append(("primaryClass", primary_class))
    if doi:
        fields.append(("doi", doi))
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
    copy_bibtex = "複製 biblatex" if lang == "zh" else "Copy biblatex"
    copy_bibitem = r"複製 \bibitem" if lang == "zh" else r"Copy \bibitem"
    dialog_label = "引用格式" if lang == "zh" else "Citation formats"
    choose_label = "選擇格式後可直接複製" if lang == "zh" else "Choose a format, then copy it."
    close_label = "關閉" if lang == "zh" else "Close"
    bibtex_format_label = "biblatex"
    bibitem_format_label = r"LaTeX \bibitem"
    return (
        f'<button class="publication-action pub-citation-toggle" type="button" '
        f'data-bibtex-toggle="{esc(identifier)}" data-citation-toggle="{esc(identifier)}" '
        f'aria-controls="{esc(identifier)}" aria-expanded="false">Cite</button>'
        f'<div class="citation-panel" id="{esc(identifier)}" hidden>'
        f'<div class="citation-panel-header"><div><strong>{esc(dialog_label)}</strong>'
        f'<span>{esc(choose_label)}</span></div>'
        f'<button type="button" class="citation-close" data-citation-close="{esc(identifier)}" '
        f'aria-label="{esc(close_label)}">&times;</button></div>'
        f'<div class="citation-format-tabs" role="tablist" aria-label="{esc(dialog_label)}">'
        f'<button type="button" class="citation-format-tab active" role="tab" aria-selected="true" '
        f'aria-controls="{esc(bibtex_id)}" data-citation-panel="{esc(identifier)}" '
        f'data-citation-format="bibtex"><span>biblatex</span><small>.bib</small></button>'
        f'<button type="button" class="citation-format-tab" role="tab" aria-selected="false" '
        f'aria-controls="{esc(bibitem_id)}" data-citation-panel="{esc(identifier)}" '
        f'data-citation-format="bibitem"><span>LaTeX \\bibitem</span><small>thebibliography</small></button></div>'
        f'<section class="citation-format-view" data-citation-view="bibtex" id="{esc(bibtex_id)}">'
        f'<div class="citation-toolbar"><strong>{esc(bibtex_format_label)}</strong>'
        f'<button type="button" class="citation-copy" data-copy-citation="{esc(bibtex_id)}" '
        f'data-copy-bibtex="{esc(bibtex_id)}" data-copied-label="{esc(copied_label)}">{copy_bibtex}</button></div>'
        f'<pre tabindex="0"><code>{esc(bibtex)}</code></pre></section>'
        f'<section class="citation-format-view" data-citation-view="bibitem" id="{esc(bibitem_id)}" hidden>'
        f'<div class="citation-toolbar"><strong>{esc(bibitem_format_label)}</strong>'
        f'<button type="button" class="citation-copy" data-copy-citation="{esc(bibitem_id)}" '
        f'data-copied-label="{esc(copied_label)}">{copy_bibitem}</button></div>'
        f'<pre tabindex="0"><code>{esc(bibitem)}</code></pre></section></div>'
    )

def render_publication_article(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    links_html = "".join(
        f'<a class="publication-action" href="{esc(link.get("url", ""))}" rel="noopener" target="_blank">{esc((link.get("label") or {}).get(lang) or (link.get("label") or {}).get("en") or "Link")}</a>'
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
        f'<article class="publication" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><div class="pub-year">{esc(entry.get("year"))}</div><div>'
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


def _navigation_href(data: dict[str, Any], page: dict[str, Any], lang: str, *, absolute: bool = False) -> str:
    path = str((page.get("path") or {}).get(lang) or "")
    if not path:
        return ""
    if absolute:
        return _absolute_url(current_site_settings(data)["seo"]["base_url"], path)
    return page_href(data, str(page.get("id") or ""), lang)


def render_site_navigation(
    data: dict[str, Any],
    current_page_id: str,
    lang: str,
    *,
    absolute: bool = False,
    language_button: bool = False,
) -> str:
    pages = normalized_pages(data)
    settings = current_site_settings(data)
    general = settings["general"]
    navigation_settings = general["navigation"]
    links: list[str] = []
    for page in pages:
        if page.get("show_in_navigation", True) is False:
            continue
        href = _navigation_href(data, page, lang, absolute=absolute)
        if not href:
            continue
        label = str((page.get("name") or {}).get(lang) or page.get("id") or "")
        active = str(page.get("id") or "") == current_page_id
        attrs = ' class="active" aria-current="page"' if active else ""
        links.append(f'<a{attrs} data-nav="{esc(page.get("id"))}" href="{esc(href)}">{esc(label)}</a>')

    home_page = next((page for page in pages if page.get("id") == "home"), None)
    home_href = _navigation_href(data, home_page, lang, absolute=absolute) if home_page else ""
    if home_href and navigation_settings.get("show_contact_shortcut", True):
        contact_label = "聯絡" if lang == "zh" else "Contact"
        if current_page_id == "contact":
            contact_href = _absolute_url(settings["seo"]["base_url"], "zh/contact.html" if lang == "zh" else "contact.html") if absolute else "contact.html"
            links.append(f'<a class="active" aria-current="page" data-nav="contact" href="{esc(contact_href)}">{contact_label}</a>')
        else:
            links.append(f'<a data-nav="contact" href="{esc(home_href)}#contact">{contact_label}</a>')

    if navigation_settings.get("search_enabled", True):
        placeholder = navigation_settings["search_placeholder"][lang]
        label = navigation_settings["search_label"][lang]
        index_url = _absolute_url(settings["seo"]["base_url"], "content/search-index.json") if absolute else ("../content/search-index.json" if lang == "zh" else "content/search-index.json")
        links.append(
            '<div class="site-search" data-site-search>'
            f'<label class="sr-only" for="site-search-{lang}-{esc(current_page_id or "page")}">{esc(label)}</label>'
            f'<input id="site-search-{lang}-{esc(current_page_id or "page")}" type="search" autocomplete="off" '
            f'placeholder="{esc(placeholder)}" aria-label="{esc(label)}" data-search-index="{esc(index_url)}" data-search-language="{lang}">'
            '<div class="site-search-results" data-search-results hidden></div></div>'
        )

    if language_button:
        label = "中文" if lang == "en" else "English"
        aria = "切換至中文版" if lang == "en" else "Switch to English"
        links.append(f'<button aria-label="{aria}" class="language-toggle nav-language-button" type="button" data-switch-language>{label}</button>')
    else:
        if current_page_id == "contact":
            counterpart = "../contact.html" if lang == "zh" else "zh/contact.html"
        else:
            current = next((page for page in pages if page.get("id") == current_page_id), None)
            counterpart = _counterpart_href(current, lang) if current else ""
        if counterpart:
            label = "中文" if lang == "en" else "English"
            aria = "切換至中文版" if lang == "en" else "Switch to English"
            links.append(f'<a aria-label="{aria}" class="language-toggle" href="{esc(counterpart)}">{label}</a>')
    return '<nav aria-label="Primary navigation" class="site-nav" id="site-nav-' + esc(lang) + '">' + "".join(links) + "</nav>"


def render_site_header(data: dict[str, Any], current_page_id: str, lang: str, *, absolute: bool = False, language_button: bool = False) -> str:
    general = current_site_settings(data)["general"]
    brand = general["identity"]["brand"][lang] or general["identity"]["brand"]["en"] or "HC Tsui"
    menu = general["identity"]["menu_label"][lang]
    home_page = next((page for page in normalized_pages(data) if page.get("id") == "home"), None)
    home_href = _navigation_href(data, home_page, lang, absolute=absolute) if home_page else "/"
    nav = render_site_navigation(data, current_page_id, lang, absolute=absolute, language_button=language_button)
    return (
        '<header class="site-header"><div class="container nav-wrap">'
        f'<a class="brand" href="{esc(home_href)}">{esc(brand)}</a>'
        f'<button aria-controls="site-nav-{lang}" aria-expanded="false" class="menu-button" type="button">{esc(menu)}</button>'
        f'{nav}</div></header>'
    )

def replace_navigation(text: str, data: dict[str, Any], current_page_id: str, lang: str) -> str:
    header = render_site_header(data, current_page_id, lang)
    updated, count = re.subn(r'<header\b(?=[^>]*\bclass="[^"]*\bsite-header\b[^"]*")[^>]*>.*?</header>', lambda _: header, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not replace site header/navigation")
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
    return f'<article class="teaching-card" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><div class="date">{term}</div><div><h3>{course}</h3>{f"<p class=\"venue\">{role}</p>" if role else ""}{links_html}</div></article>'


def render_interest(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    desc = rich_html(plain_value(entry, "description", lang))
    return f'<article class="interest-summary-item" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</article>'


def render_education(entry: dict[str, Any], lang: str) -> str:
    when = plain_value(entry, "date_label", lang) or display_range(entry)
    title = linked_title(entry, lang)
    org = rich_html(plain_value(entry, "organization", lang))
    desc = rich_html(plain_value(entry, "description", lang))
    detail = " · ".join(x for x in (org, desc) if x)
    return f'<article id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><time>{esc(when)}</time><div><h3>{title}</h3>{f"<p>{detail}</p>" if detail else ""}</div></article>'


def render_generic(entry: dict[str, Any], lang: str) -> str:
    title = linked_title(entry, lang)
    desc = rich_html(plain_value(entry, "description", lang))
    when = plain_value(entry, "date_label", lang) or display_range(entry)
    return f'<article class="timeline-item" data-entry-id="{esc(entry.get("id"))}"><time>{esc(when)}</time><div><h3>{title}</h3>{f"<p>{desc}</p>" if desc else ""}</div></article>'


def render_contact(items: list[dict[str, Any]], lang: str, *, extra_card: str = "") -> str:
    cards = []
    inserted = False
    for entry in items:
        title = rich_html(plain_value(entry, "title", lang))
        value = rich_html(plain_value(entry, "description", lang))
        url = str(entry.get("url") or "").strip()
        body = f'<a href="{esc(url)}" rel="noopener">{value}</a>' if url else f'<p>{value}</p>'
        entry_id = str(entry.get("id") or "")
        row_class = ' class="contact-location"' if entry_id == "contact-address-office" else ""
        cards.append(f'<div{row_class} data-entry-id="{esc(entry_id)}"><span>{title}</span>{body}</div>')
        if extra_card and str(entry.get("id") or "") == "contact-affiliation":
            cards.append(extra_card)
            inserted = True
    if extra_card and not inserted:
        cards.insert(max(0, len(cards) - 1), extra_card)
    return '<div class="contact-grid">' + "".join(cards) + '</div>'


def contact_form_home_card(data: dict[str, Any], lang: str) -> str:
    config = current_site_settings(data).get("contact_form", {})
    if not config.get("enabled"):
        return ""
    title = "聯絡表單" if lang == "zh" else "Contact Form"
    label = "填寫" if lang == "zh" else "Fill out"
    href = "contact.html"
    return (
        '<div class="contact-form-entry" data-system-entry="contact-form">'
        f'<span>{title}</span><a href="{href}">{label}</a></div>'
    )


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


def render_contact_form(data: dict[str, Any], lang: str) -> str:
    config = current_site_settings(data).get("contact_form", {})
    if not config.get("enabled"):
        return ""
    mode = str(config.get("mode") or "email_only")
    endpoint = "https://api.web3forms.com/submit" if mode == "email_only" else str(config.get("worker_url") or "")
    if not endpoint:
        return ""
    title = esc(config.get("title", {}).get(lang) or "")
    intro = esc(config.get("intro", {}).get(lang) or "")
    labels = {key: esc(config.get(key, {}).get(lang) or "") for key in ("name_label", "email_label", "subject_label", "message_label", "submit_label", "success_message", "privacy_note")}
    hidden = ''
    fixed_subject = str(config.get("email_subject") or "[hctsui.github.io] New contact message").strip()
    if mode == "email_only":
        hidden += f'<input type="hidden" name="access_key" value="{esc(config.get("web3forms_access_key") or "")}">'
        hidden += f'<input type="hidden" name="subject" value="{esc(fixed_subject)}">'
        hidden += '<input type="hidden" name="from_name" value="hctsui.github.io contact form">'
    else:
        hidden += f'<input type="hidden" name="email_subject" value="{esc(fixed_subject)}">'
    hidden += '<input type="checkbox" name="botcheck" tabindex="-1" autocomplete="off" class="contact-botcheck" aria-hidden="true">'
    turnstile = ""
    if mode == "worker" and config.get("turnstile_site_key"):
        turnstile = f'<div class="cf-turnstile" data-sitekey="{esc(config["turnstile_site_key"])}" data-size="flexible"></div><script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
    intro_html = f"<p>{intro}</p>" if intro else ""
    privacy_html = f'<p class="contact-form-privacy">{labels["privacy_note"]}</p>' if labels["privacy_note"] else ""
    return (
        f'<div class="contact-form-shell"><h3>{title}</h3>{intro_html}'
        f'<form class="contact-form" method="post" action="{esc(endpoint)}" data-contact-form data-contact-mode="{esc(mode)}" data-success-message="{labels["success_message"]}">'
        f'{hidden}<div class="contact-form-grid"><label>{labels["name_label"]}<input name="name" required maxlength="160" autocomplete="name"></label>'
        f'<label>{labels["email_label"]}<input type="email" name="email" required maxlength="320" autocomplete="email"></label></div>'
        f'<label>{labels["subject_label"]}<input name="visitor_subject" maxlength="240"></label>'
        f'<label>{labels["message_label"]}<textarea name="message" required maxlength="8000" rows="6"></textarea></label>'
        f'{turnstile}<button class="button primary contact-submit" type="submit">{labels["submit_label"]}</button>'
        f'<p class="contact-form-status" role="status" aria-live="polite"></p>{privacy_html}'
        f'</form></div>'
    )


def contact_system_page() -> dict[str, Any]:
    return {
        "id": "contact",
        "name": {"en": "Contact", "zh": "聯絡"},
        "path": {"en": "contact.html", "zh": "zh/contact.html"},
        "languages": ["en", "zh"],
        "header": None,
        "color": "#8d493d",
        "show_in_navigation": False,
        "order": 999,
    }


def apply_contact_page_design(text: str, design: dict[str, Any]) -> str:
    colors = design.get("colors", {})
    accent = str(colors.get("accent") or "#8d493d")
    style = ";".join(
        [
            page_theme_style(accent),
            f"--contact-bg:{colors.get('background', '#f7f3ed')}",
            f"--contact-surface:{colors.get('surface', '#ffffff')}",
            f"--contact-accent:{accent}",
            f"--contact-text:{colors.get('text', '#2d2926')}",
            f"--contact-muted:{colors.get('muted', '#6c625c')}",
            f"--contact-button:{colors.get('button', accent)}",
            f"--contact-button-text:{colors.get('button_text', '#ffffff')}",
            f"--bg:{colors.get('background', '#f7f3ed')}",
            f"--surface:{colors.get('surface', '#ffffff')}",
            f"--surface-alt:{colors.get('surface', '#ffffff')}",
            f"--ink:{colors.get('text', '#2d2926')}",
            f"--muted:{colors.get('muted', '#6c625c')}",
        ]
    )
    return re.sub(r'(<body\b[^>]*?)(?:\sstyle="[^"]*")?(>)', rf'\1 style="{style}"\2', text, count=1)


def render_contact_page_main(data: dict[str, Any], lang: str) -> str:
    config = current_site_settings(data)["contact_form"]
    design = config["page_design"]
    eyebrow = rich_html(design["eyebrow"][lang])
    title = rich_html(design["title"][lang])
    description = rich_html(design["description"][lang])
    form = render_contact_form(data, lang)
    if not form:
        unavailable = "聯絡表單目前尚未開放。" if lang == "zh" else "The contact form is currently unavailable."
        form = f'<div class="contact-form-unavailable">{esc(unavailable)}</div>'
    return (
        '<section class="contact-page-hero"><div class="container">'
        f'<p class="section-label">{eyebrow}</p><h1>{title}</h1><p>{description}</p>'
        '</div></section>'
        '<section class="contact-page-section"><div class="container contact-page-container">'
        f'{form}</div></section>'
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
        f'<div>{render_contact(items, lang, extra_card=contact_form_home_card(data, lang))}</div></div></section>'
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


def render_home_cover(data: dict[str, Any], lang: str) -> str:
    cover = current_site_settings(data)["general"]["cover"]
    image = str(cover.get("image") or "assets/images/photo-960.webp")
    fallback = str(cover.get("fallback") or "assets/images/photo.jpg")
    prefix = "../" if lang == "zh" else ""
    def rel(path: str) -> str:
        return path if re.match(r"^https?://", path, flags=re.I) else prefix + path
    image_url = rel(image)
    fallback_url = rel(fallback)
    srcset = ""
    match = re.fullmatch(r"assets/images/(.+?)-(640|960|1440)\.(webp|avif|jpg|jpeg|png)", image, flags=re.I)
    if match:
        stem, _, ext = match.groups()
        candidates = []
        for width in (640, 960, 1440):
            candidate = ROOT / f"assets/images/{stem}-{width}.{ext}"
            if candidate.exists():
                candidates.append(f"{rel(candidate.relative_to(ROOT).as_posix())} {width}w")
        if candidates:
            srcset = f' srcset="{esc(", ".join(candidates))}" sizes="(max-width: 800px) 100vw, 45vw"'
    candidates = "|".join(dict.fromkeys([image_url, fallback_url]))
    return (
        '<div class="home-visual"><div class="home-visual-panel"><figure class="home-portrait">'
        f'<img alt="{esc(cover["alt"][lang])}" data-photo-candidates="{esc(candidates)}" decoding="async" '
        f'fetchpriority="high" src="{esc(image_url)}"{srcset} style="object-position:{esc(cover["object_position"])}">'
        f'<figcaption>{esc(cover["caption"][lang])}</figcaption></figure></div></div>'
    )


def apply_home_cover(hero: str, data: dict[str, Any], lang: str) -> str:
    cover = render_home_cover(data, lang)
    updated, count = re.subn(r'<div class="home-visual">.*?</div></div></div></section>', lambda _: cover + '</div></section>', hero, count=1, flags=re.S)
    if count == 1:
        return updated
    return hero

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


def render_robots_txt(data: dict[str, Any]) -> str:
    base_url = current_site_settings(data)["seo"]["base_url"].rstrip("/")
    return "\n".join(
        (
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /dossier.html",
            "Disallow: /zh/dossier.html",
            "Disallow: /content/",
            "Disallow: /cv/",
            "Disallow: /integrations/",
            "Disallow: /tests/",
            "Disallow: /tools/",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        )
    )


def render_sitemap_xml(data: dict[str, Any]) -> str:
    settings = current_site_settings(data)["seo"]
    pages = [*normalized_pages(data), contact_system_page()]
    urls: list[str] = []
    for page in pages:
        if str(page.get("id") or "") not in INDEXABLE_PAGE_IDS:
            continue
        for lang in ("en", "zh"):
            rel_path = str((page.get("path") or {}).get(lang) or "")
            if not rel_path:
                continue
            canonical_path = rel_path[:-10] if rel_path.endswith("index.html") else rel_path
            url = _absolute_url(settings["base_url"], "", canonical_path)
            if url not in urls:
                urls.append(url)
    body = "\n".join(f"  <url><loc>{esc(url)}</loc></url>" for url in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def write_search_engine_files(data: dict[str, Any]) -> list[Path]:
    changed: list[Path] = []
    for path, content in (
        (ROOT / "robots.txt", render_robots_txt(data)),
        (ROOT / "sitemap.xml", render_sitemap_xml(data)),
    ):
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if old != content:
            path.write_text(content, encoding="utf-8")
            changed.append(path)
    return changed


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


_CLOUDFLARE_ANALYTICS_START = "<!-- managed:cloudflare-web-analytics -->"
_CLOUDFLARE_ANALYTICS_END = "<!-- /managed:cloudflare-web-analytics -->"
_GOOGLE_ANALYTICS_START = "<!-- managed:google-analytics -->"
_GOOGLE_ANALYTICS_END = "<!-- /managed:google-analytics -->"


def _remove_managed_analytics(text: str) -> str:
    for start, end in (
        (_CLOUDFLARE_ANALYTICS_START, _CLOUDFLARE_ANALYTICS_END),
        (_GOOGLE_ANALYTICS_START, _GOOGLE_ANALYTICS_END),
    ):
        pattern = re.escape(start) + r".*?" + re.escape(end) + r"\s*"
        text = re.sub(pattern, "", text, flags=re.S)
    return text


def apply_analytics(text: str, data: dict[str, Any]) -> str:
    """Insert the selected analytics provider only in generated public pages."""
    text = _remove_managed_analytics(text)
    analytics = current_site_settings(data)["analytics"]
    if not analytics.get("enabled"):
        return text
    provider = analytics.get("provider")
    if provider == "cloudflare" and analytics.get("cloudflare_token"):
        payload = json.dumps({"token": analytics["cloudflare_token"]}, separators=(",", ":"))
        block = (
            f"{_CLOUDFLARE_ANALYTICS_START}\n"
            '<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" '
            f"data-cf-beacon='{esc(payload)}'></script>\n"
            f"{_CLOUDFLARE_ANALYTICS_END}"
        )
        return text.replace("</body>", block + "\n</body>", 1)
    if provider == "google" and analytics.get("google_measurement_id"):
        measurement_id = esc(analytics["google_measurement_id"])
        block = (
            f"{_GOOGLE_ANALYTICS_START}\n"
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>\n'
            '<script>\n'
            '  window.dataLayer = window.dataLayer || [];\n'
            '  function gtag(){dataLayer.push(arguments); }\n'
            '  gtag("js", new Date());\n'
            f'  gtag("config", "{measurement_id}");\n'
            '</script>\n'
            f"{_GOOGLE_ANALYTICS_END}"
        )
        match = re.search(r"<head\b[^>]*>", text, flags=re.I)
        if match:
            return text[: match.end()] + "\n" + block + text[match.end() :]
        return text
    return text


def apply_cloudflare_analytics(text: str, data: dict[str, Any]) -> str:
    """Backward-compatible alias for the site analytics injector."""
    return apply_analytics(text, data)


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


def apply_static_asset_paths(text: str, lang: str) -> str:
    prefix = "../" if lang == "zh" else ""
    patterns = {
        r"(?:\.\./)?assets/favicon\.svg": f"{prefix}assets/images/favicon.svg",
        r"(?:\.\./)?assets/photo-640\.webp": f"{prefix}assets/images/photo-640.webp",
        r"(?:\.\./)?assets/photo-960\.webp": f"{prefix}assets/images/photo-960.webp",
        r"(?:\.\./)?assets/photo-1440\.webp": f"{prefix}assets/images/photo-1440.webp",
        r"(?<!assets/images/)(?:\.\./)?photo\.jpg": f"{prefix}assets/images/photo.jpg",
    }
    for pattern, replacement in patterns.items():
        text = re.sub(pattern, replacement, text)
    return text


def apply_page_theme(text: str, page: dict[str, Any]) -> str:
    style = page_theme_style(str(page.get("color") or ""))
    return re.sub(r'(<body\b[^>]*?)(?:\sstyle="[^"]*")?(>)', rf'\1 style="{style}"\2', text, count=1)


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
    secondary = {lang: _absolute_url(base, error["secondary_url"][lang]) for lang in ("en", "zh")}
    css_url = _absolute_url(base, "assets/style.css")
    script_url = _absolute_url(base, "assets/script.js")
    favicon_url = _absolute_url(base, "assets/images/favicon.svg")
    language_payload = json.dumps({"home": home, "redirect": error["auto_redirect"]}, ensure_ascii=False, separators=(",", ":"))

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
            secondary_button = f'<a class="not-found-button secondary" href="{esc(secondary[lang])}">{esc(error["secondary_label"][lang])}</a>'
        footer = render_footer(data, lang, today) if error["show_footer"] else ""
        header = render_site_header(data, "404", lang, absolute=True, language_button=True) if error["show_navigation"] else ""
        return f'''<div class="not-found-language" data-language="{lang}" hidden>
          {header}
          <main class="not-found-main" id="main-{lang}">
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
  <link rel="icon" href="{esc(favicon_url)}" type="image/svg+xml">
  <link rel="stylesheet" href="{esc(css_url)}">
  <script defer src="{esc(script_url)}"></script>
  <style>
    :root{{--nf-background:{colors["background"]};--nf-surface:{colors["surface"]};--nf-accent:{colors["accent"]};--nf-text:{colors["text"]};--nf-muted:{colors["muted"]};--nf-button:{colors["button"]};--nf-button-text:{colors["button_text"]}}}
    body{{margin:0;background:var(--nf-background);color:var(--nf-text)}}
    .not-found-language{{min-height:100vh;display:flex;flex-direction:column}}
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
    .nav-language-button{{font:inherit;cursor:pointer}}
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
    return apply_analytics(page, data)


def site_today(data: dict[str, Any], override: str | None = None) -> date:
    value = override or os.environ.get("SITE_TODAY", "")
    if value:
        return date.fromisoformat(value)
    return datetime.now(ZoneInfo(data.get("settings", {}).get("timezone", "Asia/Tokyo"))).date()


def build(today: date, update_date: bool = True) -> list[Path]:
    data = load_data()
    assign_citation_keys(data)
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
                content = apply_home_cover(extract_home_hero(old), data, lang) + sections
            else:
                rendered = [render_category(data, c, lang, today, i) for i, c in enumerate(categories)]
                sections = "".join(x for x in rendered if x)
                content = page_header(data, page_id, lang) + sections
            new = replace_main(old, content)
            new = replace_navigation(new, data, page_id, lang)
            new = apply_static_asset_paths(new, lang)
            new = apply_page_theme(new, page)
            new = apply_seo_metadata(new, data, page, lang)
            updated_value = f"{today.year}/{today.month}/{today.day}" if update_date else _existing_updated(old, lang, today)
            new = replace_footer(new, render_footer(data, lang, today, updated=updated_value))
            new = link_people_html(new, PEOPLE, lang)
            new = apply_cloudflare_analytics(new, data)
            if new != old:
                path.write_text(new, encoding="utf-8")
                changed.append(path)
    contact_page = contact_system_page()
    contact_settings = current_site_settings(data)["contact_form"]
    contact_design = contact_settings["page_design"]
    for lang in ("en", "zh"):
        rel = contact_page["path"][lang]
        path = ROOT / rel
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        path.parent.mkdir(parents=True, exist_ok=True)
        shell = custom_page_shell(contact_page, lang)
        new = replace_main(shell, render_contact_page_main(data, lang))
        new = replace_navigation(new, data, "contact", lang)
        new = apply_static_asset_paths(new, lang)
        if not contact_design.get("show_navigation", True):
            new = re.sub(r'<nav\b(?=[^>]*\bclass="[^"]*\bsite-nav\b[^"]*")[^>]*>.*?</nav>', "", new, count=1, flags=re.S)
            new = re.sub(r'<button\b(?=[^>]*\bclass="[^"]*\bmenu-button\b[^"]*")[^>]*>.*?</button>', "", new, count=1, flags=re.S)
        new = apply_contact_page_design(new, contact_design)
        new = apply_seo_metadata(new, data, contact_page, lang)
        updated_value = f"{today.year}/{today.month}/{today.day}" if update_date else _existing_updated(old, lang, today)
        if contact_design.get("show_footer", True):
            new = replace_footer(new, render_footer(data, lang, today, updated=updated_value))
        else:
            new = re.sub(r'<footer class="site-footer">.*?</footer>', "", new, count=1, flags=re.S)
        new = link_people_html(new, PEOPLE, lang)
        new = apply_analytics(new, data)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(path)

    error_path = ROOT / "404.html"
    error_old = error_path.read_text(encoding="utf-8") if error_path.exists() else ""
    error_new = render_404_page(data, today)
    if error_new != error_old:
        error_path.write_text(error_new, encoding="utf-8")
        changed.append(error_path)
    changed.extend(write_search_engine_files(data))
    from build_media_manifest import main as build_media_manifest
    from build_search_index import main as build_search_index
    build_media_manifest()
    build_search_index()
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
