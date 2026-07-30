#!/usr/bin/env python3
"""Managed page/category model shared by Admin, website, and PDF CV."""
from __future__ import annotations

import copy
import re
from typing import Any

PAGE_DEFAULTS: list[dict[str, Any]] = [
    {"id": "home", "name": {"en": "Home", "zh": "首頁"}, "path": {"en": "index.html", "zh": "zh/index.html"}, "header": None, "order": 0},
    {"id": "cv", "name": {"en": "CV", "zh": "履歷"}, "path": {"en": "cv.html", "zh": "zh/cv.html"}, "header": {"label": {"en": "Academic profile", "zh": "學術資料"}, "title": {"en": "Curriculum Vitae", "zh": "履歷"}, "intro": {"en": "Education, research interests, and honors.", "zh": "學歷、研究領域與獎項"}}, "order": 1},
    {"id": "publications", "name": {"en": "Publications", "zh": "論文"}, "path": {"en": "publications.html", "zh": "zh/publications.html"}, "header": {"label": {"en": "Research record", "zh": "研究紀錄"}, "title": {"en": "Publications and Preprints", "zh": "論文與預印本"}, "intro": {"en": "A complete list of current papers and preprints.", "zh": "論文與預印本的完整列表"}}, "order": 2},
    {"id": "activities", "name": {"en": "Activities", "zh": "學術活動"}, "path": {"en": "activities.html", "zh": "zh/activities.html"}, "header": {"label": {"en": "Academic record", "zh": "學術紀錄"}, "title": {"en": "Activities", "zh": "學術活動"}, "intro": {"en": "Academic visits, presentations, conferences and workshops.", "zh": "學術訪問、學術報告、會議與工作坊"}}, "order": 3},
    {"id": "teaching", "name": {"en": "Teaching", "zh": "教學"}, "path": {"en": "teaching.html", "zh": "zh/teaching.html"}, "header": {"label": {"en": "Teaching record", "zh": "教學紀錄"}, "title": {"en": "Teaching Experience", "zh": "教學經歷"}, "intro": {"en": "Teaching and course-assistant experience.", "zh": "教學與課程助教經歷"}}, "order": 4},
]

CATEGORY_KIND_LABELS: dict[str, dict[str, str]] = {
    "featured_publications": {"en": "Featured publications", "zh": "首頁精選論文"},
    "upcoming": {"en": "Upcoming activities", "zh": "首頁近期活動"},
    "contact": {"en": "Contact", "zh": "聯絡資訊"},
    "interest": {"en": "Research interests", "zh": "研究興趣"},
    "education": {"en": "Education", "zh": "學歷"},
    "honor": {"en": "Honors", "zh": "獎項"},
    "publication": {"en": "Publications", "zh": "論文／作品"},
    "visit": {"en": "Academic visits", "zh": "學術訪問"},
    "talk": {"en": "Presentations", "zh": "學術報告"},
    "organization": {"en": "Organization", "zh": "學術活動籌辦"},
    "conference": {"en": "Conferences", "zh": "會議／工作坊"},
    "teaching": {"en": "Teaching", "zh": "教學"},
    "personal": {"en": "Personal information", "zh": "個人資訊"},
    "generic": {"en": "General items", "zh": "一般項目"},
}

DIRECT_ITEM_KINDS = {"interest", "education", "honor", "publication", "visit", "talk", "organization", "conference", "teaching", "personal", "generic", "contact"}
DERIVED_KINDS = {"featured_publications", "upcoming"}
ALL_CATEGORY_KINDS = set(CATEGORY_KIND_LABELS)

OLD_HEADING_TO_CATEGORY = {
    "home_publications": ("home-publications", "home", "featured_publications", False),
    "home_upcoming": ("home-upcoming", "home", "upcoming", False),
    "home_contact": ("home-contact", "home", "contact", False),
    "cv_research": ("cv-research", "cv", "interest", True),
    "cv_education": ("cv-education", "cv", "education", True),
    "cv_honors": ("cv-honors", "cv", "honor", True),
    "activity_visit": ("activity-visits", "activities", "visit", True),
    "activity_talk": ("activity-talks", "activities", "talk", True),
    "activity_organization": ("activity-organization", "activities", "organization", True),
    "activity_conference": ("activity-conferences", "activities", "conference", True),
}

OLD_PAGE_HEADING_KEYS = {
    "cv": "cv_page",
    "publications": "publications_page",
    "activities": "activities_page",
    "teaching": "teaching_page",
}

DEFAULT_PROFILE_ITEMS: list[dict[str, Any]] = [
    {"id": "interest-function-field-arithmetic", "type": "interest", "category_id": "cv-research", "order": 0, "title": {"en": "Function Field Arithmetic", "zh": "函數體算術"}, "description": {"en": "", "zh": ""}},
    {"id": "interest-positive-characteristic-mzv-mes", "type": "interest", "category_id": "cv-research", "order": 1, "title": {"en": "Multiple Zeta Values and Multiple Eisenstein Series in Positive Characteristic", "zh": "正特徵下的多重 zeta 值與多重 Eisenstein 級數"}, "description": {"en": "", "zh": ""}},
    {"id": "education-phd-nthu", "type": "education", "category_id": "cv-education", "order": 0, "start_date": "2025-02-01", "end_date": "", "date_label": {"en": "Feb. 2025–Present", "zh": "2025 年 2 月至今"}, "title": {"en": "PhD in Mathematics", "zh": "數學博士班"}, "organization": {"en": "National Tsing Hua University", "zh": "國立清華大學"}, "description": {"en": "Direct admission", "zh": "逕讀博士"}},
    {"id": "education-bs-nthu", "type": "education", "category_id": "cv-education", "order": 1, "start_date": "2021-09-01", "end_date": "2024-12-31", "date_label": {"en": "Sep. 2021–Dec. 2024", "zh": "2021 年 9 月至 2024 年 12 月"}, "title": {"en": "BS in Mathematics", "zh": "數學學士"}, "organization": {"en": "National Tsing Hua University", "zh": "國立清華大學"}, "description": {"en": "Graduated with distinction", "zh": "成績優異畢業"}},
    {"id": "contact-institutional-email", "type": "contact", "category_id": "home-contact", "order": 0, "title": {"en": "Institutional email", "zh": "學校信箱"}, "description": {"en": "hctsui@gapp.nthu.edu.tw", "zh": "hctsui@gapp.nthu.edu.tw"}, "url": "mailto:hctsui@gapp.nthu.edu.tw"},
    {"id": "contact-personal-email", "type": "contact", "category_id": "home-contact", "order": 1, "title": {"en": "Personal email", "zh": "個人信箱"}, "description": {"en": "hctsui.math@gmail.com", "zh": "hctsui.math@gmail.com"}, "url": "mailto:hctsui.math@gmail.com"},
    {"id": "contact-affiliation", "type": "contact", "category_id": "home-contact", "order": 2, "title": {"en": "Affiliation", "zh": "所屬單位"}, "description": {"en": "Department of Mathematics, National Tsing Hua University, Taiwan", "zh": "臺灣國立清華大學數學系"}},
    {"id": "contact-address-office", "type": "contact", "category_id": "home-contact", "order": 3, "title": {"en": "Address & office", "zh": "地址與辦公室"}, "description": {"en": "General Building III, Room 628, 6F; No. 101, Sec. 2, Guangfu Rd., East Dist., Hsinchu City 300044, Taiwan (R.O.C.)", "zh": "國立清華大學第三綜合大樓 6 樓 628 室；300044 臺灣新竹市東區光復路二段 101 號"}},
    {"id": "personal-languages", "type": "personal", "category_id": "cv-personal", "order": 0, "title": {"en": "Language", "zh": "語言"}, "description": {"en": "Mandarin (Native) | English (CEFR C1) | Japanese (CEFR A1)", "zh": "中文（母語） | 英文（CEFR C1） | 日文（CEFR A1）"}},
    {"id": "personal-address", "type": "personal", "category_id": "cv-personal", "order": 1, "title": {"en": "Address", "zh": "地址"}, "description": {"en": "No. 101, Sec. 2, Guangfu Rd., East Dist., Hsinchu City 300044, Taiwan (R.O.C.)", "zh": "臺灣 300044 新竹市東區光復路二段 101 號"}},
    {"id": "personal-email", "type": "personal", "category_id": "cv-personal", "order": 2, "title": {"en": "Email", "zh": "電子郵件"}, "description": {"en": "hctsui@gapp.nthu.edu.tw | hctsui.math@gmail.com", "zh": "hctsui@gapp.nthu.edu.tw | hctsui.math@gmail.com"}},
    {"id": "personal-website", "type": "personal", "category_id": "cv-personal", "order": 3, "title": {"en": "Website", "zh": "網站"}, "description": {"en": "https://hctsui.github.io", "zh": "https://hctsui.github.io"}, "url": "https://hctsui.github.io"},
    {"id": "personal-orcid", "type": "personal", "category_id": "cv-personal", "order": 4, "title": {"en": "ORCID", "zh": "ORCID"}, "description": {"en": "0009-0009-7445-5634", "zh": "0009-0009-7445-5634"}, "url": "https://orcid.org/0009-0009-7445-5634"},
]


def pair(value: Any, fallback: dict[str, str] | None = None) -> dict[str, str]:
    fallback = fallback or {"en": "", "zh": ""}
    if not isinstance(value, dict):
        return copy.deepcopy(fallback)
    return {lang: str(value.get(lang) or fallback.get(lang) or "").strip() for lang in ("en", "zh")}


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text[:64] or "category"


def old_heading(settings: dict[str, Any], key: str, part: str, fallback: dict[str, str]) -> dict[str, str]:
    value = settings.get("headings", {}).get(key, {}).get(part, {})
    return pair(value, fallback)


def normalized_pages(data: dict[str, Any]) -> list[dict[str, Any]]:
    settings = data.setdefault("settings", {})
    existing = settings.get("pages")
    pages: list[dict[str, Any]] = []
    existing_map = {str(p.get("id")): p for p in existing if isinstance(p, dict) and p.get("id")} if isinstance(existing, list) else {}
    for default in PAGE_DEFAULTS:
        source = existing_map.get(default["id"], {})
        item = copy.deepcopy(default)
        item["name"] = pair(source.get("name"), default["name"])
        item["path"] = copy.deepcopy(default["path"])
        item["order"] = int(source.get("order", default["order"]))
        if default["header"] is not None:
            old_key = OLD_PAGE_HEADING_KEYS.get(default["id"])
            old = settings.get("headings", {}).get(old_key, {}) if old_key else {}
            header_source = source.get("header") if isinstance(source.get("header"), dict) else {}
            item["header"] = {
                part: pair(header_source.get(part), pair(old.get(part), default["header"][part]))
                for part in ("label", "title", "intro")
            }
        pages.append(item)
    return sorted(pages, key=lambda p: (int(p.get("order", 999)), p["id"]))


def _base_categories(data: dict[str, Any]) -> list[dict[str, Any]]:
    settings = data.setdefault("settings", {})
    headings = settings.get("headings", {}) if isinstance(settings.get("headings"), dict) else {}
    categories: list[dict[str, Any]] = []
    order_by_page: dict[str, int] = {}

    def add(category_id: str, page_id: str, kind: str, label: dict[str, str], title: dict[str, str], *, show_cv: bool = False, show_web: bool = True, intro: dict[str, str] | None = None) -> None:
        order = order_by_page.get(page_id, 0)
        order_by_page[page_id] = order + 1
        categories.append({
            "id": category_id,
            "page_id": page_id,
            "kind": kind,
            "label": pair(label),
            "title": pair(title),
            "intro": pair(intro),
            "order": order,
            "show_on_web": bool(show_web),
            "show_on_cv": bool(show_cv),
        })

    defaults = {
        "home_publications": ({"en": "Recent work", "zh": "近期成果"}, {"en": "Selected Publications", "zh": "精選論文"}),
        "home_upcoming": ({"en": "Calendar", "zh": "行程"}, {"en": "Upcoming", "zh": "近期活動"}),
        "home_contact": ({"en": "Contact", "zh": "聯絡資訊"}, {"en": "Get in touch", "zh": "聯絡"}),
        "cv_research": ({"en": "Fields", "zh": "研究方向"}, {"en": "Research Interests", "zh": "研究領域"}),
        "cv_education": ({"en": "Degrees", "zh": "學位"}, {"en": "Education", "zh": "學歷"}),
        "cv_honors": ({"en": "Recognition", "zh": "獎助紀錄"}, {"en": "Honors and Awards", "zh": "獎項與榮譽"}),
        "activity_visit": ({"en": "Visit", "zh": "訪問經歷"}, {"en": "Academic Visits", "zh": "學術訪問"}),
        "activity_talk": ({"en": "Talks", "zh": "演講紀錄"}, {"en": "Presentations", "zh": "學術報告"}),
        "activity_organization": ({"en": "Organizing Experience", "zh": "籌辦經歷"}, {"en": "Organization", "zh": "學術活動籌辦"}),
        "activity_conference": ({"en": "Participation", "zh": "參與紀錄"}, {"en": "Conferences and Workshops", "zh": "會議與工作坊"}),
    }
    for old_key, (category_id, page_id, kind, show_cv) in OLD_HEADING_TO_CATEGORY.items():
        fallback_label, fallback_title = defaults[old_key]
        add(category_id, page_id, kind, old_heading(settings, old_key, "label", fallback_label), old_heading(settings, old_key, "title", fallback_title), show_cv=show_cv)

    # Publication and teaching headings become normal categories.
    pub_label = old_heading(settings, "publication_groups", "label", {"en": "Manuscript type", "zh": "稿件類型"})
    for group in sorted(settings.get("content_groups", {}).get("publication", []), key=lambda g: (int(g.get("order", 999)), str(g.get("id", "")))):
        gid = str(group.get("id") or "")
        if not gid:
            continue
        add(f"publication-{gid}", "publications", "publication", pub_label, pair(group.get("label"), {"en": gid.replace("-", " ").title(), "zh": ""}), show_cv=True)
    teaching_label = old_heading(settings, "teaching_groups", "label", {"en": "Institution", "zh": "機構"})
    for group in sorted(settings.get("content_groups", {}).get("teaching", []), key=lambda g: (int(g.get("order", 999)), str(g.get("id", "")))):
        gid = str(group.get("id") or "")
        if not gid:
            continue
        add(f"teaching-{gid}", "teaching", "teaching", teaching_label, pair(group.get("label"), {"en": gid.replace("-", " ").title(), "zh": ""}), show_cv=True)

    add("cv-personal", "cv", "personal", {"en": "Details", "zh": "個人資料"}, old_heading(settings, "cv_personal", "title", {"en": "Personal Information", "zh": "個人資訊"}), show_cv=True, show_web=False)
    return categories


def normalized_categories(data: dict[str, Any]) -> list[dict[str, Any]]:
    settings = data.setdefault("settings", {})
    existing = settings.get("categories")
    if not isinstance(existing, list) or not existing:
        return _base_categories(data)
    page_ids = {p["id"] for p in normalized_pages(data)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(existing):
        if not isinstance(source, dict):
            continue
        cid = str(source.get("id") or "").strip()
        kind = str(source.get("kind") or "generic").strip()
        page_id = str(source.get("page_id") or "cv").strip()
        if not cid or cid in seen or kind not in ALL_CATEGORY_KINDS or page_id not in page_ids:
            continue
        seen.add(cid)
        result.append({
            "id": cid,
            "page_id": page_id,
            "kind": kind,
            "label": pair(source.get("label"), CATEGORY_KIND_LABELS[kind]),
            "title": pair(source.get("title"), CATEGORY_KIND_LABELS[kind]),
            "intro": pair(source.get("intro")),
            "order": int(source.get("order", index)),
            "show_on_web": bool(source.get("show_on_web", True)),
            "show_on_cv": bool(source.get("show_on_cv", False)),
        })
    return sorted(result, key=lambda c: (next((p["order"] for p in normalized_pages(data) if p["id"] == c["page_id"]), 999), int(c.get("order", 999)), c["id"]))


def category_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in normalized_categories(data)}


def _order_rank(data: dict[str, Any], kind: str, entry_id: str, fallback: int) -> int:
    order = data.get("settings", {}).get("entry_order", {}).get(kind, [])
    if isinstance(order, list) and entry_id in order:
        return order.index(entry_id)
    return fallback


def ensure_item_categories(data: dict[str, Any]) -> None:
    categories = category_map(data)
    # Seed formerly hard-coded profile items only during the first schema-3
    # migration.  Once migrated, they are ordinary items and may be deleted.
    seed_profile_items = int(data.get("schema_version", 0) or 0) < 3 or "profile_items" not in data
    profile = data.setdefault("profile_items", [])
    if not isinstance(profile, list):
        profile = data["profile_items"] = []
    if seed_profile_items:
        known_profile = {str(x.get("id")) for x in profile if isinstance(x, dict)}
        for item in DEFAULT_PROFILE_ITEMS:
            if item["id"] not in known_profile:
                profile.append(copy.deepcopy(item))

    for idx, entry in enumerate(data.get("activities", [])):
        kind = str(entry.get("type") or "")
        default = {
            "visit": "activity-visits",
            "talk": "activity-talks",
            "organization": "activity-organization",
            "conference": "activity-conferences",
        }.get(kind)
        if default and str(entry.get("category_id") or "") not in categories:
            entry["category_id"] = default
        entry["order"] = int(entry.get("order", _order_rank(data, kind, str(entry.get("id")), idx)))
        # Organization and conference are independent records in schema 3.
        entry.pop("show_in_organization", None)
    for idx, entry in enumerate(data.get("honors", [])):
        if str(entry.get("category_id") or "") not in categories:
            entry["category_id"] = "cv-honors"
        entry["order"] = int(entry.get("order", _order_rank(data, "honor", str(entry.get("id")), idx)))
    for idx, entry in enumerate(data.get("publications", [])):
        gid = str(entry.get("group_id") or "preprints")
        cid = f"publication-{gid}"
        if cid not in categories:
            # Preserve unexpected group by creating a category.
            label = pair(entry.get("group_label"), {"en": gid.replace("-", " ").title(), "zh": ""})
            settings = data.setdefault("settings", {})
            cats = settings.setdefault("categories", normalized_categories(data))
            cats.append({"id": cid, "page_id": "publications", "kind": "publication", "label": {"en": "Manuscript type", "zh": "稿件類型"}, "title": label, "intro": {"en": "", "zh": ""}, "order": len([c for c in cats if c.get("page_id") == "publications"]), "show_on_web": True, "show_on_cv": True})
            categories[cid] = cats[-1]
        entry["category_id"] = str(entry.get("category_id") or cid)
        if entry["category_id"] not in categories or categories[entry["category_id"]]["kind"] != "publication":
            entry["category_id"] = cid
        entry["order"] = int(entry.get("order", idx))
    for idx, entry in enumerate(data.get("teaching", [])):
        gid = str(entry.get("group_id") or "national-tsing-hua-university")
        cid = f"teaching-{gid}"
        entry["category_id"] = str(entry.get("category_id") or cid)
        if entry["category_id"] not in categories or categories[entry["category_id"]]["kind"] != "teaching":
            entry["category_id"] = cid
        entry["order"] = int(entry.get("order", idx))
    for idx, entry in enumerate(profile):
        if not isinstance(entry, dict):
            continue
        entry["order"] = int(entry.get("order", idx))


def normalized_cv_order(data: dict[str, Any]) -> list[str]:
    categories = normalized_categories(data)
    known = {c["id"] for c in categories if c.get("show_on_cv")}
    current = data.get("settings", {}).get("cv_category_order", [])
    result = [str(x) for x in current if str(x) in known] if isinstance(current, list) else []
    defaults = [
        "cv-research", "cv-education",
        *[c["id"] for c in categories if c["kind"] == "publication"],
        "activity-visits", "activity-talks", "activity-organization", "cv-honors", "activity-conferences",
        *[c["id"] for c in categories if c["kind"] == "teaching"],
        "cv-personal",
    ]
    for cid in defaults:
        if cid in known and cid not in result:
            result.append(cid)
    for cid in sorted(known):
        if cid not in result:
            result.append(cid)
    return result


def migrate_category_data(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.setdefault("settings", {})
    settings["pages"] = normalized_pages(data)
    settings["categories"] = normalized_categories(data)
    ensure_item_categories(data)
    # Re-normalize in case unexpected groups created categories.
    settings["categories"] = normalized_categories(data)
    settings["cv_category_order"] = normalized_cv_order(data)
    data["schema_version"] = max(int(data.get("schema_version", 0) or 0), 3)
    return data


def all_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *(x for x in data.get("profile_items", []) if isinstance(x, dict)),
        *(x for x in data.get("honors", []) if isinstance(x, dict)),
        *(x for x in data.get("publications", []) if isinstance(x, dict)),
        *(x for x in data.get("activities", []) if isinstance(x, dict)),
        *(x for x in data.get("teaching", []) if isinstance(x, dict)),
    ]


def items_for_category(data: dict[str, Any], category_id: str) -> list[dict[str, Any]]:
    return sorted([x for x in all_items(data) if x.get("category_id") == category_id], key=lambda x: (int(x.get("order", 999999)), str(x.get("id", ""))))


def categories_for_page(data: dict[str, Any], page_id: str, *, web_only: bool = True) -> list[dict[str, Any]]:
    rows = [c for c in normalized_categories(data) if c.get("page_id") == page_id and (not web_only or c.get("show_on_web", True))]
    return sorted(rows, key=lambda c: (int(c.get("order", 999999)), c["id"]))


def category_kind_for_item_type(item_type: str) -> str:
    return item_type if item_type in DIRECT_ITEM_KINDS else "generic"


def validate_category_data(data: dict[str, Any]) -> None:
    pages = normalized_pages(data)
    page_ids = [p["id"] for p in pages]
    if len(page_ids) != len(set(page_ids)):
        raise ValueError("settings.pages contains duplicate IDs.")
    categories = normalized_categories(data)
    category_ids = [c["id"] for c in categories]
    if len(category_ids) != len(set(category_ids)):
        raise ValueError("settings.categories contains duplicate IDs.")
    page_set = set(page_ids)
    for category in categories:
        if category["page_id"] not in page_set:
            raise ValueError(f"Category {category['id']} refers to an unknown page.")
        if category["kind"] not in ALL_CATEGORY_KINDS:
            raise ValueError(f"Category {category['id']} has an unsupported kind.")
        for field in ("label", "title"):
            for lang in ("en", "zh"):
                if not str(category.get(field, {}).get(lang) or "").strip():
                    raise ValueError(f"Category {category['id']} {field}.{lang} cannot be blank.")
    category_by_id = {c["id"]: c for c in categories}
    item_ids: set[str] = set()
    for item in all_items(data):
        iid = str(item.get("id") or "").strip()
        if not iid:
            raise ValueError("Every item must have an ID.")
        if iid in item_ids:
            raise ValueError(f"Duplicate item ID: {iid}")
        item_ids.add(iid)
        cid = str(item.get("category_id") or "")
        if cid not in category_by_id:
            raise ValueError(f"{iid}: unknown or missing category_id '{cid}'.")
        item_type = str(item.get("type") or "")
        expected = category_by_id[cid]["kind"]
        if expected in DIRECT_ITEM_KINDS and item_type != expected:
            raise ValueError(f"{iid}: type '{item_type}' does not match category kind '{expected}'.")
    cv_order = normalized_cv_order(data)
    if len(cv_order) != len(set(cv_order)):
        raise ValueError("settings.cv_category_order contains duplicates.")
