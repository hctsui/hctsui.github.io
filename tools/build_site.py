#!/usr/bin/env python3
"""Generate all bilingual website sections from managed pages and categories."""
from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

import process_request as core
from category_config import categories_for_page, items_for_category, migrate_category_data, normalized_pages
from homepage_config import homepage_activities, homepage_publications
from markup_config import rich_html as safe_rich_html, stored_rich_html
from site_settings_config import current_site_settings
from people_config import link_author_html, link_people_html, load_people
from publication_config import journal_label, normalized_journal, publication_state

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
        return stored_rich_html(rich[lang])
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


def _bibtex_escape(value: Any, *, preserve_math: bool = False) -> str:
    text = str(value or "").strip()
    if preserve_math:
        return "".join(
            part if index % 2 else part.replace("\\", r"\textbackslash{}")
            for index, part in enumerate(re.split(r"(\$[^$\n]+\$)", text))
        )
    return text.replace("\\", r"\textbackslash{}")


def publication_bibtex(entry: dict[str, Any]) -> str:
    manual = str(entry.get("bibtex") or "").strip()
    if manual:
        return manual
    authors = " and ".join(_split_english_authors(plain_value(entry, "authors", "en")))
    title = plain_value(entry, "title", "en")
    year = str(entry.get("year") or str(entry.get("date") or "")[:4] or "")
    arxiv = str(entry.get("arxiv") or "").strip()
    journal = normalized_journal(entry)
    state = publication_state(entry)
    journal_like = bool(journal["journaltitle"] or state in {"forthcoming", "published"})
    entry_type = "article" if journal_like else "online"
    fields: list[tuple[str, str]] = [("title", title), ("author", authors)]
    if journal_like:
        fields.extend((
            ("journal", journal["journaltitle"]),
            ("date", journal["date"] or year),
            ("volume", journal["volume"]),
            ("number", journal["number"]),
            ("pages", journal["pages"]),
            ("eid", journal["eid"]),
            ("doi", journal["doi"]),
        ))
        if state == "forthcoming":
            fields.append(("note", "To appear"))
    else:
        fields.append(("date", year))
        if arxiv:
            fields.extend((("eprint", arxiv), ("eprinttype", "arxiv")))
            primary_class = str(entry.get("primary_category") or entry.get("primary_class") or "").strip()
            if primary_class:
                fields.append(("eprintclass", primary_class))
    rows = [f"  {name} = {{{_bibtex_escape(value, preserve_math=name == 'title')}}}" for name, value in fields if value]
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
    plain = plain_value(entry, "title", "en")
    raw = str(plain if "data-tex-inline" in str(rich) and "$" in plain else rich or plain)
    result: list[str] = []
    position = 0
    for match in re.finditer(r"<em>(.*?)</em>|\$([^$\n]+)\$", raw, flags=re.I | re.S):
        before = re.sub(r"<[^>]+>", "", raw[position:match.start()])
        result.append(_latex_citation_escape(html.unescape(before), strip=False))
        if match.group(2) is not None:
            result.append(f"${html.unescape(match.group(2))}$")
        else:
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
    journal = normalized_journal(entry)
    state = publication_state(entry)
    year = str(journal["date"][:4] or entry.get("year") or str(entry.get("date") or "")[:4] or "").strip()
    arxiv = _latex_citation_escape(str(entry.get("arxiv") or "").strip())
    doi = _latex_citation_escape(journal["doi"])

    details: list[str] = []
    label = _latex_citation_escape(journal_label(entry))
    if state == "forthcoming":
        if label:
            details.append(rf"\textbf{{{label}}}")
        details.append("to appear")
    elif state == "published" or label:
        journal_parts: list[str] = []
        if label:
            journal_parts.append(rf"\textbf{{{label}}}")
        if journal["volume"]:
            journal_parts.append(_latex_citation_escape(journal["volume"]))
        if year:
            journal_parts.append(f"({year})")
        journal_citation = " ".join(journal_parts)
        if journal["number"]:
            journal_citation += f", no. {_latex_citation_escape(journal['number'])}"
        if journal["pages"] or journal["eid"]:
            journal_citation += f", {_latex_citation_escape(journal['pages'] or journal['eid'])}"
        if journal_citation:
            details.append(journal_citation)
    else:
        if state == "submitted":
            details.append("submitted")
        elif state == "under_review":
            details.append("under review")
        if arxiv:
            details.append(f"arXiv:{arxiv}")
        if year:
            details.append(f"({year})")

    if doi:
        details.append(f"doi: {doi}")

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


PUBLICATION_OWNER_NAMES = ("Hung-Chun Tsui", "崔鴻竣")


class _PublicationOwnerEmphasisParser(HTMLParser):
    """Bold the site owner's name without changing stored author markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.strong_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")
        if tag.lower() == "strong":
            self.strong_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if tag.lower() == "strong" and self.strong_depth:
            self.strong_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.strong_depth:
            self.parts.append(data)
            return
        emphasized = data
        for name in PUBLICATION_OWNER_NAMES:
            pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
            emphasized = pattern.sub(lambda match: f"<strong>{match.group(0)}</strong>", emphasized)
        self.parts.append(emphasized)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")


def emphasize_publication_owner(fragment: str) -> str:
    """Apply owner emphasis only to a rendered publication author line."""
    if not fragment:
        return fragment
    parser = _PublicationOwnerEmphasisParser()
    parser.feed(fragment)
    parser.close()
    return "".join(parser.parts)


def render_publication_article(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    links_html = "".join(
        f'<a class="publication-action" href="{esc(link.get("url", ""))}" rel="noopener" target="_blank">{esc((link.get("label") or {}).get(lang) or (link.get("label") or {}).get("en") or "Link")}</a>'
        for link in entry.get("links", []) if link.get("url")
    )
    bibtex = bibtex_controls(entry, lang)
    links = f'<div class="pub-links">{links_html}{bibtex}</div>' if links_html or bibtex else ""
    title = (entry.get("homepage_title_html", {}) or {}).get(lang) if homepage else ""
    authors = (entry.get("homepage_authors_html", {}) or {}).get(lang) if homepage else ""
    title = stored_rich_html(title) if title else inline_value(entry, "title", lang)
    authors = stored_rich_html(authors) if authors else inline_value(entry, "authors", lang)
    authors = emphasize_publication_owner(authors)
    authors = link_author_html(authors, PEOPLE, lang)
    venue = inline_value(entry, "venue", lang)
    return (
        f'<article class="publication" id="{esc(entry.get("id"))}" data-entry-id="{esc(entry.get("id"))}"><div class="pub-year">{esc(entry.get("year"))}</div><div>'
        f'<h3>{title}</h3><p class="authors">{authors}</p><p class="venue">{venue}</p>{links}</div></article>'
    )


def _relative_page_href(target: str, current_path: str) -> str:
    current_dir = str(PurePosixPath(current_path).parent)
    return posixpath.relpath(target, "." if current_dir == "." else current_dir)


def page_href(data: dict[str, Any], page_id: str, lang: str, current_path: str = "") -> str:
    page = next((p for p in normalized_pages(data) if p["id"] == page_id), None)
    if not page:
        return ""
    target_lang = lang if page["path"].get(lang) else ("zh" if page["path"].get("zh") else "en")
    path = str(page["path"].get(target_lang) or "")
    if not path:
        return ""
    if current_path:
        return _relative_page_href(path, current_path)
    if lang == "zh":
        return _relative_page_href(path, "zh/current.html") if target_lang == "zh" else f"../{path}"
    return path


def _counterpart_href(page: dict[str, Any], lang: str, current_path: str = "") -> str:
    target_lang = "zh" if lang == "en" else "en"
    path = str((page.get("path") or {}).get(target_lang) or "")
    if not path:
        return ""
    if current_path:
        return _relative_page_href(path, current_path)
    return path if lang == "en" else f"../{path}"


def _navigation_href(data: dict[str, Any], page: dict[str, Any], lang: str, *, absolute: bool = False, current_path: str = "") -> str:
    path = str((page.get("path") or {}).get(lang) or "")
    if not path:
        return ""
    if absolute:
        return _absolute_url(current_site_settings(data)["seo"]["base_url"], path)
    return page_href(data, str(page.get("id") or ""), lang, current_path)


def render_site_navigation(
    data: dict[str, Any],
    current_page_id: str,
    lang: str,
    *,
    absolute: bool = False,
    language_button: bool = False,
    current_path: str = "",
) -> str:
    pages = normalized_pages(data)
    settings = current_site_settings(data)
    general = settings["general"]
    navigation_settings = general["navigation"]
    links: list[str] = []
    for page in pages:
        if page.get("show_in_navigation", True) is False:
            continue
        href = _navigation_href(data, page, lang, absolute=absolute, current_path=current_path)
        if not href:
            continue
        label = str((page.get("name") or {}).get(lang) or page.get("id") or "")
        active = str(page.get("id") or "") == current_page_id
        attrs = ' class="active" aria-current="page"' if active else ""
        links.append(f'<a{attrs} data-nav="{esc(page.get("id"))}" href="{esc(href)}">{esc(label)}</a>')

    home_page = next((page for page in pages if page.get("id") == "home"), None)
    home_href = _navigation_href(data, home_page, lang, absolute=absolute, current_path=current_path) if home_page else ""
    if home_href and navigation_settings.get("show_contact_shortcut", True):
        contact_label = "聯絡" if lang == "zh" else "Contact"
        if current_page_id == "contact":
            contact_path = "zh/contact.html" if lang == "zh" else "contact.html"
            contact_href = _absolute_url(settings["seo"]["base_url"], contact_path) if absolute else (_relative_page_href(contact_path, current_path) if current_path else "contact.html")
            links.append(f'<a class="active" aria-current="page" data-nav="contact" href="{esc(contact_href)}">{contact_label}</a>')
        else:
            links.append(f'<a data-nav="contact" href="{esc(home_href)}#contact">{contact_label}</a>')

    if navigation_settings.get("search_enabled", True):
        placeholder = navigation_settings["search_placeholder"][lang]
        label = navigation_settings["search_label"][lang]
        index_url = _absolute_url(settings["seo"]["base_url"], "content/search-index.json") if absolute else (_relative_page_href("content/search-index.json", current_path) if current_path else ("../content/search-index.json" if lang == "zh" else "content/search-index.json"))
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
            counterpart = _counterpart_href(current, lang, current_path) if current else ""
        if counterpart:
            label = "中文" if lang == "en" else "English"
            aria = "切換至中文版" if lang == "en" else "Switch to English"
            links.append(f'<a aria-label="{aria}" class="language-toggle" href="{esc(counterpart)}">{label}</a>')
    return '<nav aria-label="Primary navigation" class="site-nav" id="site-nav-' + esc(lang) + '">' + "".join(links) + "</nav>"


def render_site_header(data: dict[str, Any], current_page_id: str, lang: str, *, absolute: bool = False, language_button: bool = False, current_path: str = "") -> str:
    general = current_site_settings(data)["general"]
    brand = general["identity"]["brand"][lang] or general["identity"]["brand"]["en"] or "HC Tsui"
    menu = general["identity"]["menu_label"][lang]
    home_page = next((page for page in normalized_pages(data) if page.get("id") == "home"), None)
    home_href = _navigation_href(data, home_page, lang, absolute=absolute, current_path=current_path) if home_page else "/"
    nav = render_site_navigation(data, current_page_id, lang, absolute=absolute, language_button=language_button, current_path=current_path)
    return (
        '<header class="site-header"><div class="container nav-wrap">'
        f'<a class="brand" href="{esc(home_href)}">{esc(brand)}</a>'
        f'<button aria-controls="site-nav-{lang}" aria-expanded="false" class="menu-button" type="button">{esc(menu)}</button>'
        f'{nav}</div></header>'
    )

def replace_navigation(text: str, data: dict[str, Any], current_page_id: str, lang: str, current_path: str = "") -> str:
    header = render_site_header(data, current_page_id, lang, current_path=current_path)
    updated, count = re.subn(r'<header\b(?=[^>]*\bclass="[^"]*\bsite-header\b[^"]*")[^>]*>.*?</header>', lambda _: header, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not replace site header/navigation")
    return updated


def render_teaching(data: dict[str, Any], entry: dict[str, Any], lang: str) -> str:
    term = rich_html(plain_value(entry, "term", lang))
    course = rich_html(plain_value(entry, "course", lang))
    role = rich_html(plain_value(entry, "role", lang))
    links: list[str] = []
    external_course_url = str(entry.get("external_course_url") or "").strip()
    course_page = str(entry.get("course_page_id") or "")
    href = external_course_url or (page_href(data, course_page, lang) if course_page else "")
    if href:
        label = "課程資訊" if lang == "zh" else "Course Information"
        external = ' rel="noopener" target="_blank"' if external_course_url else ""
        links.append(f'<a href="{esc(href)}"{external}>{label}</a>')
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
