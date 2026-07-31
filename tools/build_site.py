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

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
PAGE_FILES = [ROOT / p for p in ("index.html", "cv.html", "publications.html", "activities.html", "teaching.html", "zh/index.html", "zh/cv.html", "zh/publications.html", "zh/activities.html", "zh/teaching.html")]


def load_data() -> dict[str, Any]:
    return migrate_category_data(core.migrate_data(json.loads(DATA_FILE.read_text(encoding="utf-8"))))


def esc(value: Any) -> str:
    return html.escape(str(core.strip_invisible_chars(str(value or ""))), quote=True)


def rich_html(value: Any) -> str:
    """Small safe heading/item markup: [i]x[/i], [b]x[/b], and $x$."""
    text = html.escape(str(core.strip_invisible_chars(str(value or ""))), quote=False)
    text = re.sub(r"\[i\](.+?)\[/i\]", r"<em>\1</em>", text, flags=re.I | re.S)
    text = re.sub(r"\[b\](.+?)\[/b\]", r"<strong>\1</strong>", text, flags=re.I | re.S)
    text = re.sub(r"\$([^$\n]+)\$", r"<em>\1</em>", text)
    return text


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


def render_publication_article(entry: dict[str, Any], lang: str, homepage: bool = False) -> str:
    links_html = "".join(
        f'<a href="{esc(link.get("url", ""))}" rel="noopener" target="_blank">{esc((link.get("label") or {}).get(lang) or (link.get("label") or {}).get("en") or "Link")}</a>'
        for link in entry.get("links", []) if link.get("url")
    )
    links = f'<div class="pub-links">{links_html}</div>' if links_html else ""
    title = (entry.get("homepage_title_html", {}) or {}).get(lang) if homepage else ""
    authors = (entry.get("homepage_authors_html", {}) or {}).get(lang) if homepage else ""
    title = title or inline_value(entry, "title", lang)
    authors = authors or inline_value(entry, "authors", lang)
    venue = inline_value(entry, "venue", lang)
    return (
        f'<article class="publication" data-entry-id="{esc(entry.get("id"))}"><div class="pub-year">{esc(entry.get("year"))}</div><div>'
        f'<h3>{title}</h3><p class="authors">{authors}</p><p class="venue">{venue}</p>{links}</div></article>'
    )


def render_teaching(entry: dict[str, Any], lang: str) -> str:
    term = rich_html(plain_value(entry, "term", lang))
    course = rich_html(plain_value(entry, "course", lang))
    role = rich_html(plain_value(entry, "role", lang))
    return f'<article class="teaching-card" data-entry-id="{esc(entry.get("id"))}"><div class="date">{term}</div><div><h3>{course}</h3>{f"<p class=\"venue\">{role}</p>" if role else ""}</div></article>'


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
        return '<div class="teaching-grid">' + "".join(render_teaching(x, lang) for x in items) + '</div>', len(items)
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
    updated, count = re.subn(r'<main id="main">.*?</main>', f'<main id="main">{content}</main>', text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not replace main element")
    return updated


def update_page_title(text: str, title: str) -> str:
    updated, count = re.subn(r'<title>.*?</title>', f'<title>{esc(title)}</title>', text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError("Could not update title")
    return updated


def update_footer(text: str, lang: str, today: date) -> str:
    formatted = f"{today.year}/{today.month}/{today.day}"
    pattern = r'<p>最後更新：[^<]*</p>' if lang == "zh" else r'<p>Last updated:[^<]*</p>'
    replacement = f'<p>最後更新：{formatted}</p>' if lang == "zh" else f'<p>Last updated: {formatted}</p>'
    return re.sub(pattern, replacement, text, count=1)


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
            path = ROOT / rel
            old = path.read_text(encoding="utf-8")
            categories = categories_for_page(data, page_id)
            if page_id == "home":
                sections = render_home_sections(data, categories, lang, today)
                content = extract_home_hero(old) + sections
            else:
                rendered = [render_category(data, c, lang, today, i) for i, c in enumerate(categories)]
                sections = "".join(x for x in rendered if x)
                content = page_header(data, page_id, lang) + sections
            new = replace_main(old, content)
            page_title = page.get("header", {}).get("title", {}).get(lang) if page.get("header") else ("Hung-Chun Tsui" if lang == "en" else "崔鴻竣")
            if page_id == "home":
                document_title = "Hung-Chun Tsui | Mathematics" if lang == "en" else "崔鴻竣｜數學"
            else:
                document_title = f"{page_title} | Hung-Chun Tsui"
            new = update_page_title(new, document_title)
            if update_date:
                new = update_footer(new, lang, today)
            if new != old:
                path.write_text(new, encoding="utf-8")
                changed.append(path)
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
