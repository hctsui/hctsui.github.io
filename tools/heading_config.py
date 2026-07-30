#!/usr/bin/env python3
"""Shared defaults and helpers for managed website/CV headings."""
from __future__ import annotations

import copy
from typing import Any

HEADING_DEFAULTS: dict[str, dict[str, dict[str, str]]] = {
    "home_publications": {
        "label": {"en": "Recent work", "zh": "近期成果"},
        "title": {"en": "Selected Publications", "zh": "精選論文"},
    },
    "home_upcoming": {
        "label": {"en": "Calendar", "zh": "行程"},
        "title": {"en": "Upcoming", "zh": "近期活動"},
    },
    "home_contact": {
        "label": {"en": "Contact", "zh": "聯絡資訊"},
        "title": {"en": "Get in touch", "zh": "聯絡"},
    },
    "cv_page": {
        "label": {"en": "Academic profile", "zh": "學術資料"},
        "title": {"en": "Curriculum Vitae", "zh": "履歷"},
        "intro": {"en": "Education, research interests, and honors.", "zh": "學歷、研究領域與獎項"},
    },
    "cv_research": {
        "label": {"en": "Fields", "zh": "研究方向"},
        "title": {"en": "Research Interests", "zh": "研究領域"},
    },
    "cv_education": {
        "label": {"en": "Degrees", "zh": "學位"},
        "title": {"en": "Education", "zh": "學歷"},
    },
    "cv_honors": {
        "label": {"en": "Recognition", "zh": "獎助紀錄"},
        "title": {"en": "Honors and Awards", "zh": "獎項與榮譽"},
    },
    "cv_personal": {
        "title": {"en": "Personal Information", "zh": "個人資訊"},
    },
    "publications_page": {
        "label": {"en": "Research record", "zh": "研究紀錄"},
        "title": {"en": "Publications and Preprints", "zh": "論文與預印本"},
        "intro": {"en": "A complete list of current papers and preprints.", "zh": "論文與預印本的完整列表"},
    },
    "publication_groups": {
        "label": {"en": "Manuscript type", "zh": "稿件類型"},
    },
    "activities_page": {
        "label": {"en": "Academic record", "zh": "學術紀錄"},
        "title": {"en": "Activities", "zh": "學術活動"},
        "intro": {
            "en": "Academic visits, presentations, conferences and workshops.",
            "zh": "學術訪問、學術報告、會議與工作坊",
        },
    },
    "activity_visit": {
        "label": {"en": "Visit", "zh": "訪問經歷"},
        "title": {"en": "Academic Visits", "zh": "學術訪問"},
    },
    "activity_talk": {
        "label": {"en": "Talks", "zh": "演講紀錄"},
        "title": {"en": "Presentations", "zh": "學術報告"},
    },
    "activity_organization": {
        "label": {"en": "Organizing Experience", "zh": "籌辦經歷"},
        "title": {"en": "Organization", "zh": "學術活動籌辦"},
    },
    "activity_conference": {
        "label": {"en": "Participation", "zh": "參與紀錄"},
        "title": {"en": "Conferences and Workshops", "zh": "會議與工作坊"},
    },
    "teaching_page": {
        "label": {"en": "Teaching record", "zh": "教學紀錄"},
        "title": {"en": "Teaching Experience", "zh": "教學經歷"},
        "intro": {"en": "Teaching and course-assistant experience.", "zh": "教學與課程助教經歷"},
    },
    "teaching_groups": {
        "label": {"en": "Institution", "zh": "機構"},
    },
}


def normalized_headings(value: Any) -> dict[str, dict[str, dict[str, str]]]:
    result = copy.deepcopy(HEADING_DEFAULTS)
    if not isinstance(value, dict):
        return result
    for key, parts in value.items():
        if key not in result or not isinstance(parts, dict):
            continue
        for part, pair in parts.items():
            if part not in result[key] or not isinstance(pair, dict):
                continue
            for lang in ("en", "zh"):
                text = pair.get(lang)
                if isinstance(text, str) and text.strip():
                    result[key][part][lang] = text.strip()
    return result


def headings_from_data(data: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    return normalized_headings(data.get("settings", {}).get("headings", {}))


def heading_value(data: dict[str, Any], key: str, part: str, lang: str) -> str:
    return headings_from_data(data)[key][part][lang]


def validate_headings(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("settings.headings must be an object.")
    unknown = sorted(set(value) - set(HEADING_DEFAULTS))
    if unknown:
        raise ValueError("Unknown heading keys: " + ", ".join(unknown))
    for key, defaults in HEADING_DEFAULTS.items():
        parts = value.get(key)
        if not isinstance(parts, dict):
            raise ValueError(f"Missing heading group: {key}.")
        unknown_parts = sorted(set(parts) - set(defaults))
        if unknown_parts:
            raise ValueError(f"Unknown fields for {key}: " + ", ".join(unknown_parts))
        for part in defaults:
            pair = parts.get(part)
            if not isinstance(pair, dict):
                raise ValueError(f"Missing {key}.{part} bilingual value.")
            for lang in ("en", "zh"):
                if not isinstance(pair.get(lang), str) or not pair[lang].strip():
                    raise ValueError(f"{key}.{part}.{lang} cannot be blank.")
