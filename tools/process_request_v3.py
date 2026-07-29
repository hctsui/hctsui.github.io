#!/usr/bin/env python3
"""Safer website-form processor layered on top of process_request.py.

This wrapper preserves the existing CMS processor and only patches:
- conservative publication-title handling;
- protection against reusing an unrelated old Chinese title;
- teaching role and institution fields;
- editing teaching role and institution.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

import process_request as base

ORIGINAL_FILL_CHINESE = base.fill_chinese
ORIGINAL_EDIT_ENTRY = base.edit_entry

base.FIELD_LABELS.update({
    "role": "教學身分",
    "institution": "機構",
})

ROLE_FIXED: dict[str, dict[str, str]] = {
    "teaching assistant": {"en": "Teaching Assistant", "zh": "助教"},
    "lecturer": {"en": "Lecturer", "zh": "講師"},
}

INSTITUTION_SHORTCUTS: dict[str, dict[str, str]] = {
    "nthu": {"en": "NTHU", "zh": "國立清華大學"},
    "national tsing hua university": {"en": "National Tsing Hua University", "zh": "國立清華大學"},
    "tohoku university": {"en": "Tohoku University", "zh": "東北大學"},
    "national taiwan university": {"en": "National Taiwan University", "zh": "國立臺灣大學"},
    "academia sinica": {"en": "Academia Sinica", "zh": "中央研究院"},
}


def chinese_mode(fields: dict[str, str]) -> str:
    return base.get(fields, "Chinese handling / 中文欄位處理").strip()


def copy_publication_title_mode(fields: dict[str, str]) -> bool:
    mode = chinese_mode(fields).casefold()
    return mode.startswith("keep english title") or "中文題目留空時照抄英文" in mode


def normalize_zh(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", base.strip_markup(value), flags=re.UNICODE)


def title_pairs(data: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for section in ("activities", "honors", "publications", "teaching"):
        for item in data.get(section, []):
            for field in ("title", "course"):
                pair = item.get(field)
                if not isinstance(pair, dict):
                    continue
                en = str(pair.get("en") or "").strip()
                zh = str(pair.get("zh") or "").strip()
                if en and zh:
                    pairs.append((en, zh))
    return pairs


def unrelated_reused_title(data: dict[str, Any], english: str, chinese: str) -> str:
    """Return the old English title if Chinese exactly matches an unrelated title."""
    current_en = base.normalized_text(english)
    current_zh = normalize_zh(chinese)
    if not current_en or not current_zh:
        return ""
    for old_en, old_zh in title_pairs(data):
        if normalize_zh(old_zh) != current_zh:
            continue
        old_norm = base.normalized_text(old_en)
        if not old_norm or old_norm == current_en:
            continue
        similarity = SequenceMatcher(None, current_en, old_norm).ratio()
        if similarity < 0.55:
            return old_en
    return ""


def fill_chinese(
    data: dict[str, Any],
    kind: str,
    fields: dict[str, str],
    pairs: dict[str, tuple[str, str]],
) -> dict[str, str]:
    """Use the old translator, but make publication titles conservative."""
    work_pairs = dict(pairs)
    resolved: dict[str, str] = {}
    translated_fields = dict(fields)

    # Default publication mode: leave the English title unchanged on the
    # Chinese page. Other fields (authors/status) may still use exact memory or
    # AI translation.
    if kind == "publication" and copy_publication_title_mode(fields) and "title" in work_pairs:
        en, zh = work_pairs.pop("title")
        if zh.strip():
            resolved["title"] = zh.strip()
        else:
            resolved["title"] = en.strip()
            base.NOTES.append("中文論文題目留空，因此依設定原樣使用英文題目。")
        translated_fields["Chinese handling / 中文欄位處理"] = (
            "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
        )

    if work_pairs:
        resolved.update(ORIGINAL_FILL_CHINESE(data, kind, translated_fields, work_pairs))

    # A model must never silently reuse the exact Chinese title of an unrelated
    # older paper/talk. This was the source of the observed u-MZV title error.
    for key, (english, supplied_chinese) in pairs.items():
        if supplied_chinese.strip() or key not in {"title", "course"}:
            continue
        candidate = resolved.get(key, "")
        old_english = unrelated_reused_title(data, english, candidate)
        if old_english:
            base.NOTES[:] = [note for note in base.NOTES if candidate not in note]
            resolved[key] = english.strip()
            base.WARNINGS.append(
                "自動中文題目與一筆無關舊資料完全相同，已拒絕該翻譯並改為照抄英文。"
                f"（舊英文：{old_english}）"
            )

    return resolved


def resolve_role(data: dict[str, Any], fields: dict[str, str], *, edit: bool = False) -> dict[str, str] | None:
    label = "New teaching role / 新教學身分" if edit else "Role / 教學身分"
    selected = base.get(fields, label, not edit).strip()
    if edit and (not selected or selected.startswith("Keep unchanged") or selected.startswith("維持不變")):
        return None

    lowered = selected.casefold()
    for prefix, pair in ROLE_FIXED.items():
        if lowered.startswith(prefix):
            return dict(pair)

    if lowered.startswith("other") or "其他" in selected:
        en_label = "New custom role (English) / 新自訂身分英文" if edit else "Custom role (English) / 自訂身分英文"
        zh_label = "New custom role (Chinese) / 新自訂身分中文" if edit else "Custom role (Chinese) / 自訂身分中文"
        en = base.get(fields, en_label, True)
        zh = base.get(fields, zh_label)
        if not zh:
            if not base.auto_chinese(fields):
                raise ValueError("Custom role Chinese is blank while manual Chinese mode is selected.")
            translated_fields = dict(fields)
            translated_fields["Chinese handling / 中文欄位處理"] = (
                "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
            )
            zh = fill_chinese(data, "teaching", translated_fields, {"role": (en, "")})["role"]
        return {"en": en, "zh": zh}

    raise ValueError(f"Unknown teaching role option: {selected}")


def resolve_institution(
    data: dict[str, Any], fields: dict[str, str], *, edit: bool = False
) -> dict[str, str] | None:
    en_label = (
        "New institution (English or shortcut) / 新機構英文或簡寫"
        if edit
        else "Institution (English or shortcut) / 機構英文或簡寫"
    )
    zh_label = "New institution (Chinese) / 新機構中文" if edit else "Institution (Chinese) / 機構中文"
    en = base.get(fields, en_label, not edit).strip()
    zh = base.get(fields, zh_label).strip()
    if edit and not en and not zh:
        return None
    if edit and not en and zh:
        return {"zh": zh}

    shortcut = INSTITUTION_SHORTCUTS.get(en.casefold())
    if shortcut:
        return {"en": shortcut["en"], "zh": zh or shortcut["zh"]}

    if not zh and not base.auto_chinese(fields):
        raise ValueError("Institution Chinese is blank while manual Chinese mode is selected.")
    translated_fields = dict(fields)
    translated_fields["Chinese handling / 中文欄位處理"] = (
        "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
    )
    translated = fill_chinese(data, "teaching", translated_fields, {"institution": (en, zh)})
    return {"en": en, "zh": translated["institution"]}


def add_teaching(data: dict[str, Any], fields: dict[str, str]) -> str:
    term_en = base.get(fields, "Term (English) / 學期英文", True)
    course_en = base.get(fields, "Course (English) / 課程英文", True)
    base.ensure_not_duplicate(data, "teaching", term_en, course_en)

    translated = fill_chinese(data, "teaching", fields, {
        "term": (term_en, base.get(fields, "Term (Chinese) / 學期中文")),
        "course": (course_en, base.get(fields, "Course (Chinese) / 課程中文")),
    })
    role = resolve_role(data, fields) or ROLE_FIXED["teaching assistant"]
    institution = resolve_institution(data, fields) or INSTITUTION_SHORTCUTS["nthu"]

    place_top = base.yes(base.get(fields, "Place at top? / 是否放在最前面", True))
    if place_top:
        for item in data["teaching"]:
            item["order"] = int(item.get("order", 0)) + 1
        order = 0
    else:
        order = max([int(item.get("order", -1)) for item in data["teaching"]] + [-1]) + 1

    entry = {
        "id": base.unique_id(data, "teaching", str(order), course_en),
        "type": "teaching",
        "order": order,
        "role": role,
        "institution": institution,
        "term": {"en": term_en, "zh": translated["term"]},
        "course": {"en": course_en, "zh": translated["course"]},
    }
    data["teaching"].append(entry)
    return entry["id"]


def edit_entry(data: dict[str, Any], fields: dict[str, str]) -> str:
    entry_id = ORIGINAL_EDIT_ENTRY(data, fields)
    _, item = base.locate(data, entry_id)
    if item.get("type") != "teaching":
        return entry_id

    role = resolve_role(data, fields, edit=True)
    institution = resolve_institution(data, fields, edit=True)
    if role is not None:
        item["role"] = role
    if institution is not None:
        item.setdefault("institution", {}).update(institution)
    return entry_id


# Patch only the selected extension points. base.process() resolves these globals
# at runtime, so all original form types continue to work unchanged.
base.fill_chinese = fill_chinese
base.add_teaching = add_teaching
base.edit_entry = edit_entry


if __name__ == "__main__":
    base.main()
