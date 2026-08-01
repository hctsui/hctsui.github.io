#!/usr/bin/env python3
"""Shared schema extensions for personal profile, mixed categories and placements.

This module deliberately patches the current category_config module at runtime,
so the update can be layered on top of the latest CMS without replacing the
large, frequently changing core files.
"""
from __future__ import annotations

import copy
import json
from typing import Any

PROFILE_CATEGORY_ID = "personal-profile"
MIXED_KIND = "mixed"

PROFILE_DEFAULTS: dict[str, Any] = {
    "schema_version": 1,
    "name": {"en": "Hung-Chun Tsui", "zh": "崔鴻竣"},
    "affiliation": {"en": "", "zh": ""},
    "position": {"en": "PhD Student", "zh": "博士生"},
    "institutional_email": "",
    "personal_email": "",
    "website": "https://hctsui.github.io",
    "orcid": "",
    "address": {"en": "", "zh": ""},
    "office": {"en": "", "zh": ""},
    "languages": {"en": "", "zh": ""},
}

_INSTALLED = False
_ORIGINALS: dict[str, Any] = {}


def _pair(value: Any, fallback: dict[str, str] | None = None) -> dict[str, str]:
    fallback = fallback or {"en": "", "zh": ""}
    source = value if isinstance(value, dict) else {}
    return {
        lang: str(source[lang] if lang in source else fallback.get(lang, "")).strip()
        for lang in ("en", "zh")
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _find_item(data: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    for item in data.get("profile_items", []):
        if isinstance(item, dict) and str(item.get("id") or "") == item_id:
            return item
    return None


def _description(data: dict[str, Any], item_id: str) -> dict[str, str]:
    item = _find_item(data, item_id) or {}
    return _pair(item.get("description"))


def personal_profile(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.setdefault("settings", {})
    source = settings.get("personal_profile") if isinstance(settings.get("personal_profile"), dict) else {}
    seo_name = settings.get("seo", {}).get("site_name", {})
    affiliation = _description(data, "contact-affiliation")
    position = _description(data, "profile-position")
    if not (position.get("en") or position.get("zh")):
        position = copy.deepcopy(PROFILE_DEFAULTS["position"])
    institutional = _find_item(data, "contact-institutional-email") or {}
    personal = _find_item(data, "contact-personal-email") or {}
    website = _find_item(data, "personal-website") or {}
    orcid = _find_item(data, "personal-orcid") or {}
    address = _description(data, "personal-address")
    office = _description(data, "contact-address-office")
    languages = _description(data, "personal-languages")
    result = {
        "schema_version": 1,
        "name": _pair(source.get("name"), _pair(seo_name, PROFILE_DEFAULTS["name"])),
        "affiliation": _pair(source.get("affiliation"), affiliation),
        "position": _pair(source.get("position"), position),
        "institutional_email": _text(source.get("institutional_email") or institutional.get("description", {}).get("en")),
        "personal_email": _text(source.get("personal_email") or personal.get("description", {}).get("en")),
        "website": _text(source.get("website") or website.get("description", {}).get("en") or website.get("url") or PROFILE_DEFAULTS["website"]),
        "orcid": _text(source.get("orcid") or orcid.get("description", {}).get("en")),
        "address": _pair(source.get("address"), address),
        "office": _pair(source.get("office"), office),
        "languages": _pair(source.get("languages"), languages),
    }
    return result


def normalize_profile(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    fallback = personal_profile(data or {"settings": {}, "profile_items": []})
    value = value if isinstance(value, dict) else {}
    return {
        "schema_version": 1,
        "name": _pair(value.get("name"), fallback["name"]),
        "affiliation": _pair(value.get("affiliation"), fallback["affiliation"]),
        "position": _pair(value.get("position"), fallback["position"]),
        "institutional_email": _text(value.get("institutional_email") if "institutional_email" in value else fallback["institutional_email"]),
        "personal_email": _text(value.get("personal_email") if "personal_email" in value else fallback["personal_email"]),
        "website": _text(value.get("website") if "website" in value else fallback["website"]),
        "orcid": _text(value.get("orcid") if "orcid" in value else fallback["orcid"]),
        "address": _pair(value.get("address"), fallback["address"]),
        "office": _pair(value.get("office"), fallback["office"]),
        "languages": _pair(value.get("languages"), fallback["languages"]),
    }


def _placement(category_id: str, order: int) -> dict[str, Any]:
    return {"category_id": category_id, "order": int(order)}


def normalize_placements(value: Any, *, primary: str = "", known: set[str] | None = None) -> list[dict[str, Any]]:
    known = known or set()
    rows = value if isinstance(value, list) else []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if isinstance(row, str):
            category_id, order = row, index
        elif isinstance(row, dict):
            category_id = str(row.get("category_id") or "")
            try:
                order = int(row.get("order", index))
            except (TypeError, ValueError):
                order = index
        else:
            continue
        if not category_id or category_id == primary or category_id in seen:
            continue
        if known and category_id not in known:
            continue
        seen.add(category_id)
        result.append(_placement(category_id, order))
    result.sort(key=lambda row: (row["category_id"], row["order"]))
    return result


def ensure_profile_category(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.setdefault("settings", {})
    categories = settings.setdefault("categories", [])
    category = next((row for row in categories if isinstance(row, dict) and row.get("id") == PROFILE_CATEGORY_ID), None)
    if category is None:
        same_page = [row for row in categories if isinstance(row, dict) and row.get("page_id") == "cv"]
        category = {
            "id": PROFILE_CATEGORY_ID,
            "page_id": "cv",
            "kind": MIXED_KIND,
            "label": {"en": "Profile", "zh": "個人資料"},
            "title": {"en": "Personal Information", "zh": "個人資料"},
            "intro": {"en": "", "zh": ""},
            "order": len(same_page),
            "show_on_web": False,
            "show_on_cv": False,
        }
        categories.append(category)
    else:
        category["kind"] = MIXED_KIND
        category.setdefault("page_id", "cv")
        category.setdefault("label", {"en": "Profile", "zh": "個人資料"})
        category.setdefault("title", {"en": "Personal Information", "zh": "個人資料"})
        category.setdefault("intro", {"en": "", "zh": ""})
        category.setdefault("show_on_web", False)
        category.setdefault("show_on_cv", False)
    return category


def _upsert(profile_items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    item = next((row for row in profile_items if isinstance(row, dict) and row.get("id") == item_id), None)
    if item is None:
        item = {"id": item_id}
        profile_items.append(item)
    return item


def _sync_identity_settings(data: dict[str, Any], previous: dict[str, Any], profile: dict[str, Any]) -> None:
    """Update managed identity metadata without touching publication authors."""
    settings = data.setdefault("settings", {})
    seo = settings.setdefault("seo", {})
    seo["site_name"] = copy.deepcopy(profile["name"])
    replacements = {
        lang: (str(previous.get("name", {}).get(lang) or ""), str(profile["name"].get(lang) or ""))
        for lang in ("en", "zh")
    }
    for row in (seo.get("pages", {}) or {}).values():
        if not isinstance(row, dict):
            continue
        for field in ("title", "description", "og_title", "og_description"):
            pair_value = row.get(field)
            if not isinstance(pair_value, dict):
                continue
            for lang, (old, new) in replacements.items():
                if old and new and old != new and isinstance(pair_value.get(lang), str):
                    pair_value[lang] = pair_value[lang].replace(old, new)
    for row in settings.get("footer", {}).get("items", []):
        text = row.get("text") if isinstance(row, dict) else None
        if not isinstance(text, dict):
            continue
        for lang, (old, new) in replacements.items():
            if old and new and old != new and isinstance(text.get(lang), str):
                text[lang] = text[lang].replace(old, new)


def _set_item(
    item: dict[str, Any],
    *,
    item_type: str,
    title: dict[str, str],
    description: dict[str, str],
    personal_key: str,
    display_style: str,
    url: str = "",
    placements: list[dict[str, Any]] | None = None,
    order: int = 0,
) -> None:
    item.update({
        "type": item_type,
        "category_id": PROFILE_CATEGORY_ID,
        "order": order,
        "title": _pair(title),
        "description": _pair(description),
        "personal_key": personal_key,
        "display_style": display_style,
        "display_placements": copy.deepcopy(placements or []),
    })
    if url:
        item["url"] = url
    else:
        item.pop("url", None)


def sync_personal_profile(data: dict[str, Any], value: Any | None = None) -> dict[str, Any]:
    """Store one canonical profile and synchronize every managed profile item."""
    previous = personal_profile(data)
    profile = normalize_profile(value if value is not None else previous, data)
    settings = data.setdefault("settings", {})
    settings["personal_profile"] = copy.deepcopy(profile)
    _sync_identity_settings(data, previous, profile)
    ensure_profile_category(data)
    profile_items = data.setdefault("profile_items", [])
    if not isinstance(profile_items, list):
        profile_items = data["profile_items"] = []

    # Preserve every former display location before moving the source item into
    # the one Personal Information category. The affiliation is intentionally
    # not repeated in Contact; it belongs to the fixed Dossier Profile card.
    managed_ids = {
        "profile-name", "contact-affiliation", "profile-position",
        "contact-institutional-email", "contact-personal-email", "contact-address-office",
        "personal-languages", "personal-address", "personal-email", "personal-website", "personal-orcid",
    }
    for item in profile_items:
        if not isinstance(item, dict):
            continue
        if item.get("id") in managed_ids or item.get("type") in {"personal", "contact"}:
            old_category = str(item.get("category_id") or "")
            old_order = int(item.get("order", 999999))
            placements = normalize_placements(item.get("display_placements"), primary=PROFILE_CATEGORY_ID)
            if old_category and old_category != PROFILE_CATEGORY_ID:
                keep_old = not (str(item.get("id") or "") == "contact-affiliation" and old_category == "home-contact")
                if keep_old and not any(row["category_id"] == old_category for row in placements):
                    placements.append(_placement(old_category, old_order))
            item["display_placements"] = placements
            item["category_id"] = PROFILE_CATEGORY_ID

    email_values = [x for x in (profile["institutional_email"], profile["personal_email"]) if x]
    combined_email = " | ".join(email_values)
    website_url = profile["website"]
    orcid_url = f"https://orcid.org/{profile['orcid']}" if profile["orcid"] and not profile["orcid"].startswith("http") else profile["orcid"]

    rows = [
        ("profile-name", "personal", {"en": "Name", "zh": "姓名"}, profile["name"], "name", "contact", "", [], 0),
        ("contact-affiliation", "personal", {"en": "Affiliation", "zh": "所屬單位"}, profile["affiliation"], "affiliation", "contact", "", [], 1),
        ("profile-position", "personal", {"en": "Position", "zh": "職位"}, profile["position"], "position", "contact", "", [], 2),
        ("contact-institutional-email", "contact", {"en": "Institutional email", "zh": "學校信箱"}, {"en": profile["institutional_email"], "zh": profile["institutional_email"]}, "institutional_email", "contact", f"mailto:{profile['institutional_email']}" if profile["institutional_email"] else "", [_placement("home-contact", 0)], 3),
        ("contact-personal-email", "contact", {"en": "Personal email", "zh": "個人信箱"}, {"en": profile["personal_email"], "zh": profile["personal_email"]}, "personal_email", "contact", f"mailto:{profile['personal_email']}" if profile["personal_email"] else "", [_placement("home-contact", 1)], 4),
        ("contact-address-office", "contact", {"en": "Address & office", "zh": "地址與辦公室"}, profile["office"], "office", "contact", "", [_placement("home-contact", 2)], 5),
        ("personal-languages", "personal", {"en": "Languages", "zh": "語言"}, profile["languages"], "languages", "personal", "", [_placement("cv-personal", 0)], 6),
        ("personal-address", "personal", {"en": "Address", "zh": "地址"}, profile["address"], "address", "personal", "", [_placement("cv-personal", 1)], 7),
        ("personal-email", "personal", {"en": "Email", "zh": "電子郵件"}, {"en": combined_email, "zh": combined_email}, "email", "personal", "", [_placement("cv-personal", 2)], 8),
        ("personal-website", "personal", {"en": "Website", "zh": "網站"}, {"en": website_url, "zh": website_url}, "website", "personal", website_url, [_placement("cv-personal", 3)], 9),
        ("personal-orcid", "personal", {"en": "ORCID", "zh": "ORCID"}, {"en": profile["orcid"], "zh": profile["orcid"]}, "orcid", "personal", orcid_url, [_placement("cv-personal", 4)], 10),
    ]
    for args in rows:
        item = _upsert(profile_items, args[0])
        # Preserve user-added extra placements, but enforce the managed defaults.
        previous = normalize_placements(item.get("display_placements"), primary=PROFILE_CATEGORY_ID)
        merged = {row["category_id"]: row for row in previous}
        for row in args[7]:
            merged.setdefault(row["category_id"], row)
        if args[0] == "contact-affiliation":
            merged.pop("home-contact", None)
        _set_item(
            item,
            item_type=args[1],
            title=args[2],
            description=args[3],
            personal_key=args[4],
            display_style=args[5],
            url=args[6],
            placements=list(merged.values()),
            order=args[8],
        )

    # The old contact affiliation must not appear in the Contact category.
    affiliation_item = _find_item(data, "contact-affiliation")
    if affiliation_item:
        affiliation_item["display_placements"] = [
            row for row in normalize_placements(affiliation_item.get("display_placements"), primary=PROFILE_CATEGORY_ID)
            if row["category_id"] != "home-contact"
        ]
    return profile


def normalized_dossier_order(data: dict[str, Any]) -> list[str]:
    settings = data.setdefault("settings", {})
    categories = [row for row in settings.get("categories", []) if isinstance(row, dict)]
    eligible = {
        str(row.get("id")) for row in categories
        if row.get("id") != PROFILE_CATEGORY_ID
        and row.get("kind") not in {"featured_publications", "upcoming", "contact"}
    }
    current = settings.get("dossier_category_order")
    if isinstance(current, list):
        result = [str(value) for value in current if str(value) in eligible]
    else:
        defaults = {"interest", "education", "honor", "publication", "talk", "teaching"}
        cv_order = settings.get("cv_category_order", [])
        kind_by_id = {str(row.get("id") or ""): str(row.get("kind") or "") for row in categories}
        result = [str(value) for value in cv_order if str(value) in eligible and kind_by_id.get(str(value)) in defaults]
        for row in categories:
            cid = str(row.get("id") or "")
            if row.get("kind") in defaults and cid in eligible and cid not in result:
                result.append(cid)
    settings["dossier_category_order"] = list(dict.fromkeys(result))
    return settings["dossier_category_order"]


def _display_copy(item: dict[str, Any], category_id: str, order: int) -> dict[str, Any]:
    result = copy.deepcopy(item)
    source_id = str(item.get("id") or "")
    result["_source_id"] = source_id
    result["_display_category_id"] = category_id
    result["id"] = f"{source_id}--at--{category_id}"
    result["category_id"] = category_id
    result["order"] = order
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    import category_config as cc

    cc.CATEGORY_KIND_LABELS[MIXED_KIND] = {"en": "Mixed general content", "zh": "一般內容（不限風格）"}
    cc.ALL_CATEGORY_KINDS.add(MIXED_KIND)

    original_migrate = cc.migrate_category_data
    original_items_for_category = cc.items_for_category
    _ORIGINALS.update(migrate=original_migrate, items_for_category=original_items_for_category)

    def migrate(data: dict[str, Any]) -> dict[str, Any]:
        result = original_migrate(data)
        sync_personal_profile(result)
        # Re-normalize after adding the profile category and items.
        result.setdefault("settings", {})["categories"] = cc.normalized_categories(result)
        known = {row["id"] for row in result["settings"]["categories"]}
        for item in cc.all_items(result):
            item["display_placements"] = normalize_placements(
                item.get("display_placements"), primary=str(item.get("category_id") or ""), known=known
            )
        normalized_dossier_order(result)
        return result

    def items_for_category(data: dict[str, Any], category_id: str) -> list[dict[str, Any]]:
        primary = list(original_items_for_category(data, category_id))
        seen = {str(item.get("id") or "") for item in primary}
        extra: list[dict[str, Any]] = []
        for item in cc.all_items(data):
            source_id = str(item.get("id") or "")
            if not source_id or source_id in seen:
                continue
            for row in normalize_placements(item.get("display_placements"), primary=str(item.get("category_id") or "")):
                if row["category_id"] == category_id:
                    extra.append(_display_copy(item, category_id, row["order"]))
                    break
        return sorted(primary + extra, key=lambda row: (int(row.get("order", 999999)), str(row.get("id") or "")))

    cc.migrate_category_data = migrate
    cc.items_for_category = items_for_category
    _INSTALLED = True


def patch_build_site(module: Any) -> None:
    """Teach the existing build_site module how to render a mixed category."""
    if getattr(module, "_cms_extensions_patched", False):
        return
    original = module.category_body
    original_apply_home_cover = module.apply_home_cover

    def apply_home_cover(hero: str, data: dict[str, Any], lang: str) -> str:
        result = original_apply_home_cover(hero, data, lang)
        profile = personal_profile(data)
        other = "zh" if lang == "en" else "en"
        name = module.esc(profile["name"].get(lang) or profile["name"].get(other) or "")
        secondary = module.esc(profile["name"].get(other) or "")
        name_html = f'<h1 class="home-name">{name}' + (f'<span class="home-name-zh">{secondary}</span>' if secondary else "") + "</h1>"
        result = __import__("re").sub(r'<h1 class="home-name">.*?</h1>', lambda _: name_html, result, count=1, flags=__import__("re").S)
        for css_class, key in (("home-kicker", "affiliation"), ("home-role", "position")):
            value = module.esc(profile[key].get(lang) or profile[key].get(other) or "")
            pattern = rf'<p class="{css_class}">.*?</p>'
            replacement = f'<p class="{css_class}">{value}</p>' if value else ""
            result = __import__("re").sub(pattern, lambda _: replacement, result, count=1, flags=__import__("re").S)
        email = profile.get("institutional_email") or profile.get("personal_email") or ""
        if email:
            email_href = "mailto:" + module.esc(email)
            result = __import__("re").sub(
                r'(<a\b[^>]*href=")mailto:[^"]+("[^>]*>Email</a>)',
                lambda match: match.group(1) + email_href + match.group(2),
                result,
                count=1,
            )
        orcid = str(profile.get("orcid") or "").strip()
        if orcid:
            href = orcid if orcid.startswith(("http://", "https://")) else f"https://orcid.org/{orcid}"
            escaped_href = module.esc(href)
            result = __import__("re").sub(
                r'(<a\b[^>]*href=")https?://orcid\.org/[^"]+("[^>]*>ORCID</a>)',
                lambda match: match.group(1) + escaped_href + match.group(2),
                result,
                count=1,
            )
        return result

    module.apply_home_cover = apply_home_cover

    def render_one(data: dict[str, Any], item: dict[str, Any], lang: str) -> str:
        style = str(item.get("display_style") or item.get("type") or "generic")
        if style == "publication":
            return '<ol class="publication-list mixed-block"><li>' + module.render_publication_article(item, lang) + "</li></ol>"
        if style == "teaching":
            return '<div class="teaching-grid mixed-block">' + module.render_teaching(data, item, lang) + "</div>"
        if style == "education":
            return '<div class="compact-list mixed-block">' + module.render_education(item, lang) + "</div>"
        if style == "interest":
            return '<div class="interest-summary mixed-block">' + module.render_interest(item, lang) + "</div>"
        if style == "honor":
            return '<div class="timeline compact-timeline mixed-block">' + module.render_honor(item, lang) + "</div>"
        if style in {"visit", "talk", "conference"}:
            return '<div class="timeline compact-timeline mixed-block">' + module.render_activity(item, lang) + "</div>"
        if style == "organization":
            return '<div class="timeline organization-timeline mixed-block">' + module.render_organization(item, lang) + "</div>"
        if style in {"contact", "personal"}:
            return '<div class="mixed-block">' + module.render_contact([item], lang) + "</div>"
        return '<div class="timeline mixed-block">' + module.render_generic(item, lang) + "</div>"

    def category_body(data: dict[str, Any], category: dict[str, Any], lang: str, today: Any) -> tuple[str, int]:
        if category.get("kind") != MIXED_KIND:
            return original(data, category, lang, today)
        items = module.category_items(data, category, today)
        return '<div class="mixed-content">' + "".join(render_one(data, item, lang) for item in items) + "</div>", len(items)

    module.category_body = category_body
    module._cms_extensions_patched = True


def dump_profile(value: dict[str, Any]) -> str:
    return json.dumps(normalize_profile(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
