#!/usr/bin/env python3
"""Build bilingual Academic Dossier pages from the current CMS data."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "content" / "site.json"

DEFAULT_PAGE = {
    "id": "dossier",
    "name": {"en": "Dossier", "zh": "審查資料"},
    "path": {"en": "dossier.html", "zh": "zh/dossier.html"},
    "header": {
        "label": {"en": "Academic dossier", "zh": "審查資料"},
        "title": {"en": "Academic Dossier", "zh": "學術審查資料"},
        "intro": {
            "en": "A concise overview of research, publications, talks, teaching, and academic background.",
            "zh": "彙整研究、論文、報告、教學與學術背景的審查資料。",
        },
    },
    "color": "#5b5876",
    "show_in_navigation": False,
    "order": 99,
    "languages": ["en", "zh"],
}


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def pair(value: Any, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or value.get("zh") or "")
    return str(value or "")


def plain(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def dossier_page(data: dict[str, Any]) -> dict[str, Any]:
    for page in data.get("settings", {}).get("pages", []):
        if isinstance(page, dict) and page.get("id") == "dossier":
            merged = json.loads(json.dumps(DEFAULT_PAGE))
            for key in ("name", "path", "header"):
                if isinstance(page.get(key), dict):
                    merged[key].update(page[key])
            for key in ("color", "show_in_navigation", "order", "languages"):
                if key in page:
                    merged[key] = page[key]
            return merged
    return json.loads(json.dumps(DEFAULT_PAGE))


def seo(data: dict[str, Any], page: dict[str, Any], lang: str) -> dict[str, str]:
    settings = data.get("settings", {})
    seo_data = settings.get("seo", {})
    row = seo_data.get("pages", {}).get("dossier", {})
    header = page.get("header") or {}
    title = pair(row.get("title"), lang) or pair(header.get("title"), lang)
    description = pair(row.get("description"), lang) or pair(header.get("intro"), lang)
    og_title = pair(row.get("og_title"), lang) or title
    og_description = pair(row.get("og_description"), lang) or description
    base = str(seo_data.get("base_url") or "https://hctsui.github.io").rstrip("/")
    image = str(row.get("og_image") or seo_data.get("default_image") or "assets/images/photo-1440.webp")
    if not image.startswith(("http://", "https://")):
        image = f"{base}/{image.lstrip('/')}"
    site_name = pair(seo_data.get("site_name"), lang) or ("崔鴻竣" if lang == "zh" else "Hung-Chun Tsui")
    return {
        "title": title,
        "description": description,
        "og_title": og_title,
        "og_description": og_description,
        "base": base,
        "image": image,
        "site_name": site_name,
    }


def item_title(item: dict[str, Any], lang: str) -> str:
    for field in ("title", "course", "course_title", "name", "label"):
        value = pair(item.get(field), lang)
        if value:
            return plain(value)
    return str(item.get("id") or "")


def item_meta(item: dict[str, Any], lang: str) -> str:
    values: list[str] = []
    if item.get("type") == "honor":
        values.append(str(item.get("year") or ""))
    elif item.get("type") == "teaching":
        values.append(pair(item.get("term"), lang))
    else:
        start = str(item.get("start_date") or item.get("date") or "")
        end = str(item.get("end_date") or "")
        values.append(start if not end or end == start else f"{start}–{end}")
    for field in ("authors", "venue", "organization", "institution", "description", "role"):
        value = plain(pair(item.get(field), lang))
        if value and value not in values:
            values.append(value)
    return " · ".join(value for value in values if value)


def item_links(item: dict[str, Any], lang: str) -> str:
    rows: list[tuple[str, str]] = []
    for link in item.get("links", []):
        if isinstance(link, dict) and link.get("url"):
            rows.append((pair(link.get("label"), lang) or "Link", str(link["url"])))
    for label, field in (
        ("arXiv", "arxiv_url"),
        ("PDF", "pdf_url"),
        ("DOI", "doi_url"),
        ("Journal", "journal_url"),
    ):
        url = str(item.get(field) or "")
        if url and all(existing != url for _, existing in rows):
            rows.append((label, url))
    if not rows:
        return ""
    return '<span class="dossier-links">' + "".join(
        f'<a href="{esc(url)}" rel="noopener" target="_blank">{esc(label)}</a>'
        for label, url in rows
    ) + "</span>"


def entries(items: list[dict[str, Any]], lang: str, *, ordered: bool = False) -> str:
    if not items:
        return '<p class="dossier-meta">—</p>'
    tag = "ol" if ordered else "ul"
    css = "dossier-publications" if ordered else "dossier-list"
    rendered = []
    for item in items:
        title = item_title(item, lang)
        url = str(item.get("url") or "")
        heading = (
            f'<a href="{esc(url)}" rel="noopener" target="_blank">{esc(title)}</a>'
            if url else esc(title)
        )
        meta = item_meta(item, lang)
        meta_html = f'<div class="dossier-meta">{esc(meta)}</div>' if meta else ""
        rendered.append(
            '<li class="dossier-entry">'
            f"<h3>{heading}</h3>{meta_html}{item_links(item, lang)}"
            "</li>"
        )
    return f'<{tag} class="{css}">' + "".join(rendered) + f"</{tag}>"


def year_from(value: Any) -> int:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group()) if match else 0


def affiliation(data: dict[str, Any], lang: str) -> str:
    for item in data.get("profile_items", []):
        if item.get("type") == "contact" and "affiliation" in str(item.get("id") or ""):
            return pair(item.get("description"), lang)
    education = sorted(
        [item for item in data.get("profile_items", []) if item.get("type") == "education"],
        key=lambda item: str(item.get("start_date") or ""),
        reverse=True,
    )
    if not education:
        return ""
    return " · ".join(
        value for value in (
            pair(education[0].get("title"), lang),
            pair(education[0].get("organization"), lang),
        ) if value
    )


def navigation(data: dict[str, Any], page: dict[str, Any], lang: str) -> str:
    zh = lang == "zh"
    pages = [p for p in data.get("settings", {}).get("pages", []) if isinstance(p, dict)]
    if not any(p.get("id") == "dossier" for p in pages):
        pages.append(page)
    pages.sort(key=lambda p: int(p.get("order", 999)))
    links = []
    for current in pages:
        if current.get("show_in_navigation") is False:
            continue
        path = pair(current.get("path"), lang)
        if not path:
            continue
        if zh and path.startswith("zh/"):
            path = path[3:]
        label = pair(current.get("name"), lang) or str(current.get("id") or "")
        links.append(f'<a data-nav="{esc(current.get("id"))}" href="{esc(path)}">{esc(label)}</a>')
    links.append(f'<a data-nav="contact" href="index.html#contact">{"聯絡" if zh else "Contact"}</a>')
    search_path = "../content/search-index.json" if zh else "content/search-index.json"
    search_id = f"site-search-{lang}-dossier"
    links.append(
        f'<div class="site-search" data-site-search><label class="sr-only" for="{search_id}">'
        f'{"搜尋這個網站" if zh else "Search this website"}</label>'
        f'<input id="{search_id}" type="search" autocomplete="off" '
        f'placeholder="{"搜尋" if zh else "Search"}" '
        f'aria-label="{"搜尋這個網站" if zh else "Search this website"}" '
        f'data-search-index="{search_path}" data-search-language="{lang}">'
        '<div class="site-search-results" data-search-results hidden></div></div>'
    )
    links.append(
        f'<a class="language-toggle" href="{"../dossier.html" if zh else "zh/dossier.html"}">'
        f'{"English" if zh else "中文"}</a>'
    )
    brand = pair(data.get("settings", {}).get("general", {}).get("identity", {}).get("brand"), lang) or "HC Tsui"
    menu = "選單" if zh else "Menu"
    aria = "主要導覽" if zh else "Primary navigation"
    return (
        f'<header class="site-header"><div class="container nav-wrap"><a class="brand" href="index.html">{esc(brand)}</a>'
        f'<button aria-controls="site-nav-{lang}" aria-expanded="false" class="menu-button" type="button">{menu}</button>'
        f'<nav aria-label="{aria}" class="site-nav" id="site-nav-{lang}">' + "".join(links) + "</nav></div></header>"
    )


def footer(data: dict[str, Any], lang: str) -> str:
    rows = data.get("settings", {}).get("footer", {}).get("items", [])
    if not rows:
        return f'<footer class="site-footer"><div class="container footer-inner"><span>{date.today().year} Hung-Chun Tsui</span></div></footer>'
    zones = {"left": [], "center": [], "right": []}
    for row in rows:
        text = pair(row.get("text"), lang)
        text = text.replace("{year}", str(date.today().year)).replace("{updated}", date.today().isoformat())
        if not text:
            continue
        url = str(row.get("url") or "")
        body = f'<a href="{esc(url)}">{esc(text)}</a>' if url else f"<span>{esc(text)}</span>"
        zones.setdefault(str(row.get("alignment") or "center"), []).append(f'<span class="footer-item">{body}</span>')
    return (
        '<footer class="site-footer"><div class="container footer-inner">'
        f'<div class="footer-zone footer-left">{"".join(zones["left"])}</div>'
        f'<div class="footer-zone footer-center">{"".join(zones["center"])}</div>'
        f'<div class="footer-zone footer-right">{"".join(zones["right"])}</div>'
        "</div></footer>"
    )


def analytics(data: dict[str, Any]) -> str:
    settings = data.get("settings", {}).get("analytics", {})
    if not settings.get("enabled"):
        return ""
    if settings.get("provider") == "google" and settings.get("google_measurement_id"):
        measurement = esc(settings["google_measurement_id"])
        return (
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={measurement}"></script>'
            f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
            f"gtag('js',new Date());gtag('config','{measurement}');</script>"
        )
    token = str(settings.get("cloudflare_token") or settings.get("token") or "")
    if token:
        return (
            '<!-- managed:cloudflare-web-analytics -->'
            '<script type="module" src="https://static.cloudflareinsights.com/beacon.min.js" '
            f"data-cf-beacon='{{\"token\":\"{esc(token)}\"}}'></script>"
            '<!-- /managed:cloudflare-web-analytics -->'
        )
    return ""


def render(data: dict[str, Any], page: dict[str, Any], lang: str) -> str:
    zh = lang == "zh"
    prefix = "../" if zh else ""
    page_seo = seo(data, page, lang)
    path = pair(page.get("path"), lang)
    canonical = f'{page_seo["base"]}/{path.lstrip("/")}'
    alternate = f'{page_seo["base"]}/{"dossier.html" if zh else "zh/dossier.html"}'
    profile_items = data.get("profile_items", [])
    interests = [item for item in profile_items if item.get("type") == "interest"]
    education = sorted([item for item in profile_items if item.get("type") == "education"], key=lambda item: str(item.get("start_date") or ""), reverse=True)
    contacts = [item for item in profile_items if item.get("type") == "contact"]
    honors = sorted(data.get("honors", []), key=lambda item: int(item.get("year") or 0), reverse=True)
    publications = sorted(data.get("publications", []), key=lambda item: str(item.get("date") or ""), reverse=True)
    talks = sorted([item for item in data.get("activities", []) if item.get("type") == "talk"], key=lambda item: str(item.get("start_date") or ""), reverse=True)[:6]
    teaching = sorted(data.get("teaching", []), key=lambda item: (year_from(pair(item.get("term"), "en")), pair(item.get("term"), "en")), reverse=True)[:6]
    header = page.get("header") or {}
    labels = {
        "profile": "基本資料" if zh else "Profile",
        "research": "研究領域" if zh else "Research Interests",
        "contact": "聯絡方式" if zh else "Contact",
        "education": "學歷" if zh else "Education",
        "honors": "獎項與榮譽" if zh else "Honors and Awards",
        "publications": "論文與預印本" if zh else "Publications and Preprints",
        "talks": "近期學術報告" if zh else "Recent Talks",
        "teaching": "近期教學經歷" if zh else "Recent Teaching",
    }
    current_affiliation = affiliation(data, lang)
    profile_html = f'<p><strong>{"姓名" if zh else "Name"}：</strong>{"崔鴻竣" if zh else "Hung-Chun Tsui"}</p>'
    if current_affiliation:
        profile_html += f'<p><strong>{"目前身分與機構" if zh else "Current position and affiliation"}：</strong>{esc(current_affiliation)}</p>'
    cv_href = "../files/Hung-Chun-Tsui-CV-zh.pdf" if zh else "files/Hung-Chun-Tsui-CV.pdf"
    print_label = "列印／另存 PDF" if zh else "Print / Save as PDF"
    cv_label = "開啟 PDF 履歷" if zh else "Open PDF CV"
    lang_attr = "zh-Hant" if zh else "en"
    skip = "跳至主要內容" if zh else "Skip to content"
    return f'''<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="author" content="Hung-Chun Tsui">
<title>{esc(page_seo["title"])}</title>
<link rel="icon" href="{prefix}assets/images/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}assets/style.css">
<link rel="stylesheet" href="{prefix}assets/dossier.css">
<script defer src="{prefix}assets/script.js"></script>
<script defer src="{prefix}assets/prefetch.js"></script>
<meta name="description" content="{esc(page_seo["description"])}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(page_seo["og_title"])}">
<meta property="og:description" content="{esc(page_seo["og_description"])}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(page_seo["image"])}">
<meta property="og:site_name" content="{esc(page_seo["site_name"])}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(page_seo["og_title"])}">
<meta name="twitter:description" content="{esc(page_seo["og_description"])}">
<meta name="twitter:image" content="{esc(page_seo["image"])}">
<link rel="alternate" hreflang="{lang}" href="{esc(canonical)}">
<link rel="alternate" hreflang="{'en' if zh else 'zh'}" href="{esc(alternate)}">
</head>
<body class="dossier-page" data-page="dossier" style="--accent:{esc(page.get('color') or '#5b5876')}">
<a class="skip-link" href="#main">{skip}</a>
{navigation(data, page, lang)}
<main id="main">
<section class="page-hero dossier-hero"><div class="container">
<p class="section-label">{esc(pair(header.get("label"), lang))}</p>
<h1 class="page-title">{esc(pair(header.get("title"), lang))}</h1>
<p class="page-intro">{esc(pair(header.get("intro"), lang))}</p>
<div class="dossier-actions"><button class="button primary" type="button" onclick="window.print()">{print_label}</button><a class="button" href="{cv_href}" rel="noopener" target="_blank">{cv_label}</a></div>
</div></section>
<section class="section"><div class="container dossier-grid">
<div class="dossier-column">
<section class="dossier-card"><h2>{labels["profile"]}</h2>{profile_html}</section>
<section class="dossier-card"><h2>{labels["research"]}</h2>{entries(interests, lang)}</section>
<section class="dossier-card dossier-contact"><h2>{labels["contact"]}</h2>{entries(contacts, lang)}</section>
<section class="dossier-card"><h2>{labels["education"]}</h2>{entries(education, lang)}</section>
<section class="dossier-card"><h2>{labels["honors"]}</h2>{entries(honors, lang)}</section>
</div>
<div class="dossier-column">
<section class="dossier-card"><h2>{labels["publications"]}</h2>{entries(publications, lang, ordered=True)}</section>
<section class="dossier-card"><h2>{labels["talks"]}</h2>{entries(talks, lang)}</section>
<section class="dossier-card"><h2>{labels["teaching"]}</h2>{entries(teaching, lang)}</section>
</div>
</div></section>
</main>
{footer(data, lang)}
{analytics(data)}
</body>
</html>'''


def main() -> None:
    data = json.loads(SITE.read_text(encoding="utf-8"))
    page = dossier_page(data)
    for lang in ("en", "zh"):
        relative = pair(page.get("path"), lang) or ("dossier.html" if lang == "en" else "zh/dossier.html")
        output = ROOT / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render(data, page, lang), encoding="utf-8")
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
