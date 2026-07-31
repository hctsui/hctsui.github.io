#!/usr/bin/env python3
"""Normalization and validation for editable SEO/OG metadata and footer content."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ALIGNMENTS = {"left", "center", "right"}
ICONS = {"none", "copyright", "email", "link", "github", "orcid", "location", "book", "calendar"}
PAGE_IDS = ("home", "cv", "publications", "activities", "teaching")


def _text(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _pair(value: Any, fallback: dict[str, str] | None = None, limit: int = 500) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    fallback = fallback or {"en": "", "zh": ""}
    return {
        "en": _text(source.get("en") or fallback.get("en"), limit),
        "zh": _text(source.get("zh") or fallback.get("zh"), limit),
    }


def _safe_http_url(value: Any, *, allow_relative: bool = False, allow_mailto: bool = False) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if allow_mailto and re.fullmatch(r"mailto:[^\s@]+@[^\s@]+", text, flags=re.I):
        return text
    if allow_relative and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) and not text.startswith("//"):
        return text
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc and not any(ch.isspace() for ch in text):
        return text
    return ""


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
        "schema_version": 1,
        "items": [
            {
                "id": "copyright",
                "text": {"en": "{year} Hung-Chun Tsui", "zh": "{year} Hung-Chun Tsui"},
                "url": "",
                "icon": "copyright",
                "alignment": "left",
                "new_tab": False,
            },
            {
                "id": "last-updated",
                "text": {"en": "Last updated: {updated}", "zh": "最後更新：{updated}"},
                "url": "",
                "icon": "none",
                "alignment": "right",
                "new_tab": False,
            },
        ],
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
    return {
        "schema_version": 1,
        "base_url": _safe_http_url(source.get("base_url")) or defaults["base_url"],
        "site_name": _pair(source.get("site_name"), defaults["site_name"], 120),
        "default_image": _safe_http_url(source.get("default_image"), allow_relative=True) or defaults["default_image"],
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
                "alignment": alignment if alignment in ALIGNMENTS else "center",
                "new_tab": bool(raw.get("new_tab")),
            }
        )
    return {"schema_version": 1, "items": result}


def normalized_site_settings(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        "seo": normalize_seo(source.get("seo"), data),
        "footer": normalize_footer(source.get("footer")),
    }


def current_site_settings(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    return normalized_site_settings({"seo": settings.get("seo"), "footer": settings.get("footer")}, data)


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


def site_settings_snapshot(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return copy.deepcopy(normalized_site_settings(value, data))
