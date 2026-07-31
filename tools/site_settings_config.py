#!/usr/bin/env python3
"""Normalization and validation for editable site-wide settings."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ALIGNMENTS = {"left", "center", "right"}
# Keep historical values readable, while the Admin only offers the simplified set.
ICONS = {
    "none",
    "copyright",
    "link",
    "location",
    "book",
    "calendar",
    "other",
    "email",
    "github",
    "orcid",
}
PAGE_IDS = ("home", "cv", "publications", "activities", "teaching")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
CLOUDFLARE_TOKEN = re.compile(r"^[0-9a-fA-F]{32}$")


def _text(value: Any, limit: int = 500, *, collapse: bool = True) -> str:
    raw = str(value or "").strip()
    if collapse:
        raw = re.sub(r"\s+", " ", raw)
    return raw[:limit]


def _pair(value: Any, fallback: dict[str, str] | None = None, limit: int = 500) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    fallback = fallback or {"en": "", "zh": ""}
    return {
        "en": _text(source["en"], limit) if "en" in source else _text(fallback.get("en"), limit),
        "zh": _text(source["zh"], limit) if "zh" in source else _text(fallback.get("zh"), limit),
    }


def _safe_http_url(value: Any, *, allow_relative: bool = False, allow_mailto: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if allow_mailto and re.fullmatch(r"mailto:[^\s@]+@[^\s@]+", text, flags=re.I):
        return text
    if allow_relative and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) and not text.startswith("//"):
        return text if not any(ch.isspace() for ch in text) else ""
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc and not any(ch.isspace() for ch in text):
        return text
    return ""


def _color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text.lower() if HEX_COLOR.fullmatch(text) else fallback.lower()


def default_seo(data: dict[str, Any] | None = None) -> dict[str, Any]:
    page_defaults = {
        "home": {
            "title": {"en": "Hung-Chun Tsui | Mathematics", "zh": "崔鴻竣｜數學"},
            "description": {
                "en": "Academic website of Hung-Chun Tsui, PhD student in mathematics at National Tsing Hua University.",
                "zh": "崔鴻竣的學術個人網站，收錄研究、論文、學術活動與教學經歷。",
            },
        },
        "cv": {
            "title": {"en": "Curriculum Vitae | Hung-Chun Tsui", "zh": "履歷｜崔鴻竣"},
            "description": {"en": "Curriculum vitae of Hung-Chun Tsui.", "zh": "崔鴻竣的學術履歷。"},
        },
        "publications": {
            "title": {"en": "Publications | Hung-Chun Tsui", "zh": "論文｜崔鴻竣"},
            "description": {"en": "Publications and preprints by Hung-Chun Tsui.", "zh": "崔鴻竣的論文與預印本。"},
        },
        "activities": {
            "title": {"en": "Activities | Hung-Chun Tsui", "zh": "學術活動｜崔鴻竣"},
            "description": {"en": "Academic talks, visits, conferences, and workshops of Hung-Chun Tsui.", "zh": "崔鴻竣的學術報告、訪問、會議與工作坊紀錄。"},
        },
        "teaching": {
            "title": {"en": "Teaching | Hung-Chun Tsui", "zh": "教學｜崔鴻竣"},
            "description": {"en": "Teaching experience of Hung-Chun Tsui.", "zh": "崔鴻竣的教學與課程助教經歷。"},
        },
    }
    if isinstance(data, dict):
        for page in data.get("settings", {}).get("pages", []):
            page_id = str(page.get("id") or "")
            if page_id not in page_defaults or page_id == "home":
                continue
            header = page.get("header") if isinstance(page.get("header"), dict) else {}
            title = header.get("title") if isinstance(header.get("title"), dict) else {}
            intro = header.get("intro") if isinstance(header.get("intro"), dict) else {}
            for lang in ("en", "zh"):
                if title.get(lang):
                    page_defaults[page_id]["title"][lang] = f"{title[lang]} | Hung-Chun Tsui" if lang == "en" else f"{title[lang]}｜崔鴻竣"
                if intro.get(lang):
                    page_defaults[page_id]["description"][lang] = str(intro[lang])
    pages = {}
    for page_id, values in page_defaults.items():
        pages[page_id] = {
            "title": copy.deepcopy(values["title"]),
            "description": copy.deepcopy(values["description"]),
            "og_title": {"en": "", "zh": ""},
            "og_description": {"en": "", "zh": ""},
            "og_image": "",
        }
    return {
        "schema_version": 1,
        "base_url": "https://hctsui.github.io",
        "site_name": {"en": "Hung-Chun Tsui", "zh": "崔鴻竣"},
        "default_image": "assets/photo-1440.webp",
        "pages": pages,
    }


def default_footer() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "items": [
            {
                "id": "copyright",
                "text": {"en": "{year} Hung-Chun Tsui", "zh": "{year} Hung-Chun Tsui"},
                "url": "",
                "icon": "copyright",
                "custom_icon": "",
                "alignment": "left",
                "new_tab": False,
            },
            {
                "id": "last-updated",
                "text": {"en": "Last updated: {updated}", "zh": "最後更新：{updated}"},
                "url": "",
                "icon": "none",
                "custom_icon": "",
                "alignment": "right",
                "new_tab": False,
            },
        ],
    }


def default_analytics() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": False,
        "token": "",
    }


def default_error_page() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "eyebrow": {"en": "Page not found", "zh": "找不到頁面"},
        "title": {"en": "This page does not exist.", "zh": "這個頁面不存在。"},
        "description": {
            "en": "The address may be outdated or mistyped. You can return to the homepage or continue browsing the website.",
            "zh": "網址可能已更新或輸入有誤。你可以返回首頁，或繼續瀏覽網站內容。",
        },
        "home_label": {"en": "Return home", "zh": "返回首頁"},
        "secondary_label": {"en": "View publications", "zh": "查看論文"},
        "secondary_url": {"en": "publications.html", "zh": "zh/publications.html"},
        "show_navigation": True,
        "show_footer": True,
        "auto_redirect": {"enabled": False, "seconds": 8},
        "colors": {
            "background": "#f7f3ed",
            "surface": "#ffffff",
            "accent": "#8d493d",
            "text": "#2d2926",
            "muted": "#6c625c",
            "button": "#2d2926",
            "button_text": "#ffffff",
        },
    }


def normalize_seo(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = default_seo(data)
    source = value if isinstance(value, dict) else {}
    pages_source = source.get("pages") if isinstance(source.get("pages"), dict) else {}
    page_ids = list(dict.fromkeys([*PAGE_IDS, *pages_source.keys()]))
    pages: dict[str, Any] = {}
    for page_id in page_ids:
        fallback = defaults["pages"].get(page_id, {
            "title": {"en": page_id.title(), "zh": page_id},
            "description": {"en": "", "zh": ""},
            "og_title": {"en": "", "zh": ""},
            "og_description": {"en": "", "zh": ""},
            "og_image": "",
        })
        raw = pages_source.get(page_id) if isinstance(pages_source.get(page_id), dict) else {}
        pages[page_id] = {
            "title": _pair(raw.get("title"), fallback["title"], 180),
            "description": _pair(raw.get("description"), fallback["description"], 500),
            "og_title": _pair(raw.get("og_title"), fallback.get("og_title"), 180),
            "og_description": _pair(raw.get("og_description"), fallback.get("og_description"), 500),
            "og_image": _safe_http_url(raw.get("og_image"), allow_relative=True),
        }
    base_url = _safe_http_url(source.get("base_url")) if "base_url" in source else defaults["base_url"]
    default_image = _safe_http_url(source.get("default_image"), allow_relative=True) if "default_image" in source else defaults["default_image"]
    return {
        "schema_version": 1,
        "base_url": base_url or defaults["base_url"],
        "site_name": _pair(source.get("site_name"), defaults["site_name"], 120),
        "default_image": default_image or defaults["default_image"],
        "pages": pages,
    }


def _footer_id(value: Any, index: int, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or f"footer-item-{index}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def normalize_footer(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else default_footer()
    rows = source.get("items") if isinstance(source.get("items"), list) else default_footer()["items"]
    result = []
    used: set[str] = set()
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            continue
        alignment = str(raw.get("alignment") or "center")
        icon = str(raw.get("icon") or "none")
        result.append(
            {
                "id": _footer_id(raw.get("id"), index, used),
                "text": _pair(raw.get("text"), {"en": "", "zh": ""}, 300),
                "url": _safe_http_url(raw.get("url"), allow_relative=True, allow_mailto=True),
                "icon": icon if icon in ICONS else "none",
                "custom_icon": _safe_http_url(raw.get("custom_icon"), allow_relative=True),
                "alignment": alignment if alignment in ALIGNMENTS else "center",
                "new_tab": bool(raw.get("new_tab")),
            }
        )
    return {"schema_version": 2, "items": result}


def normalize_analytics(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "schema_version": 1,
        "enabled": bool(source.get("enabled")),
        "token": _text(source.get("token"), 80),
    }


def normalize_error_page(value: Any) -> dict[str, Any]:
    defaults = default_error_page()
    source = value if isinstance(value, dict) else {}
    colors_source = source.get("colors") if isinstance(source.get("colors"), dict) else {}
    redirect_source = source.get("auto_redirect") if isinstance(source.get("auto_redirect"), dict) else {}
    secondary_url = source.get("secondary_url") if isinstance(source.get("secondary_url"), dict) else {}
    seconds_raw = redirect_source.get("seconds", defaults["auto_redirect"]["seconds"])
    try:
        seconds = int(seconds_raw)
    except (TypeError, ValueError):
        seconds = defaults["auto_redirect"]["seconds"]
    seconds = min(300, max(1, seconds))
    return {
        "schema_version": 1,
        "eyebrow": _pair(source.get("eyebrow"), defaults["eyebrow"], 120),
        "title": _pair(source.get("title"), defaults["title"], 180),
        "description": _pair(source.get("description"), defaults["description"], 600),
        "home_label": _pair(source.get("home_label"), defaults["home_label"], 100),
        "secondary_label": _pair(source.get("secondary_label"), defaults["secondary_label"], 100),
        "secondary_url": {
            "en": _safe_http_url(secondary_url.get("en"), allow_relative=True) or defaults["secondary_url"]["en"],
            "zh": _safe_http_url(secondary_url.get("zh"), allow_relative=True) or defaults["secondary_url"]["zh"],
        },
        "show_navigation": bool(source.get("show_navigation", defaults["show_navigation"])),
        "show_footer": bool(source.get("show_footer", defaults["show_footer"])),
        "auto_redirect": {
            "enabled": bool(redirect_source.get("enabled")),
            "seconds": seconds,
        },
        "colors": {
            key: _color(colors_source.get(key), fallback)
            for key, fallback in defaults["colors"].items()
        },
    }


def normalized_site_settings(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "footer": normalize_footer(source.get("footer")),
        "seo": normalize_seo(source.get("seo"), data),
        "analytics": normalize_analytics(source.get("analytics")),
        "error_page": normalize_error_page(source.get("error_page")),
    }


def current_site_settings(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    return normalized_site_settings(
        {
            "footer": settings.get("footer"),
            "seo": settings.get("seo"),
            "analytics": settings.get("analytics"),
            "error_page": settings.get("error_page"),
        },
        data,
    )


def validate_site_settings(value: Any, data: dict[str, Any] | None = None) -> None:
    normalized = normalized_site_settings(value, data)
    seo = normalized["seo"]
    base = urlparse(seo["base_url"])
    if base.scheme not in {"http", "https"} or not base.netloc:
        raise ValueError("SEO base_url must be a complete http or https URL.")
    for page_id, page in seo["pages"].items():
        for lang in ("en", "zh"):
            if not page["title"][lang]:
                raise ValueError(f"SEO title is required for {page_id}/{lang}.")
            if len(page["title"][lang]) > 180:
                raise ValueError(f"SEO title is too long for {page_id}/{lang}.")
            if len(page["description"][lang]) > 500:
                raise ValueError(f"SEO description is too long for {page_id}/{lang}.")
    footer = normalized["footer"]
    if len(footer["items"]) > 30:
        raise ValueError("Footer supports at most 30 items.")
    for item in footer["items"]:
        if not item["text"]["en"] and not item["text"]["zh"]:
            raise ValueError(f"Footer item {item['id']} needs English or Chinese text.")
        if item["icon"] == "other" and not item["custom_icon"]:
            raise ValueError(f"Footer item {item['id']} needs a custom icon path.")
    analytics = normalized["analytics"]
    if analytics["enabled"] and not CLOUDFLARE_TOKEN.fullmatch(analytics["token"]):
        raise ValueError("Cloudflare Web Analytics token must be 32 hexadecimal characters.")
    error_page = normalized["error_page"]
    for field in ("eyebrow", "title", "description", "home_label"):
        for lang in ("en", "zh"):
            if not error_page[field][lang]:
                raise ValueError(f"404 {field} is required for {lang}.")
    if error_page["auto_redirect"]["enabled"] and not (1 <= error_page["auto_redirect"]["seconds"] <= 300):
        raise ValueError("404 redirect seconds must be between 1 and 300.")


def site_settings_snapshot(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return copy.deepcopy(normalized_site_settings(value, data))
