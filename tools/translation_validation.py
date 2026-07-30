#!/usr/bin/env python3
"""Shared validation and normalization for the explicit bilingual dictionary."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


LEGACY_TRANSLATION_CATEGORIES = {
    "city_tw", "city_jp", "city_us", "state_us", "country",
    "university_tw", "university_jp", "university_us",
    "person", "course", "institution", "role", "other",
}
TAG_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def strip_limited_markup(value: str) -> str:
    return re.sub(r"\[/?(?:i|b)\]", "", value, flags=re.I).strip()


def normalize_translation(value: Any) -> str:
    text = unicodedata.normalize("NFKC", strip_limited_markup(str(value or "")))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _validate_tag_definitions(data: dict[str, Any], errors: list[str]) -> set[str]:
    definitions = data.get("tags")
    if not isinstance(definitions, list) or not definitions:
        errors.append("content/translations.json: tags must be a nonempty array.")
        return set()

    ids: set[str] = set()
    labels_en: dict[str, int] = {}
    labels_zh: dict[str, int] = {}
    for index, item in enumerate(definitions, start=1):
        if not isinstance(item, dict):
            errors.append(f"tags[{index}] must be an object")
            continue
        tag_id = str(item.get("id") or "").strip()
        if not TAG_ID_RE.fullmatch(tag_id):
            errors.append(
                f"tags[{index}].id must use lowercase letters, numbers, '-' or '_': {tag_id!r}"
            )
        elif tag_id in ids:
            errors.append(f"tags[{index}] duplicates tag id: {tag_id!r}")
        else:
            ids.add(tag_id)

        label = item.get("label")
        if not isinstance(label, dict):
            errors.append(f"tags[{index}].label must be an object with en and zh")
            continue
        en = str(label.get("en") or "").strip()
        zh = str(label.get("zh") or "").strip()
        if not en or not zh:
            errors.append(f"tags[{index}].label must contain nonblank en and zh")
            continue
        en_key = normalize_translation(en)
        zh_key = normalize_translation(zh)
        if en_key in labels_en:
            errors.append(
                f"tags[{index}] English label duplicates tags[{labels_en[en_key]}]: {en}"
            )
        else:
            labels_en[en_key] = index
        if zh_key in labels_zh:
            errors.append(
                f"tags[{index}] Chinese label duplicates tags[{labels_zh[zh_key]}]: {zh}"
            )
        else:
            labels_zh[zh_key] = index
    return ids


def validate_translation_data(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("content/translations.json must contain a JSON object.")

    schema_version = data.get("schema_version")
    if schema_version not in {1, 2}:
        raise ValueError("content/translations.json: schema_version must be 1 or 2.")

    pairs = data.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("content/translations.json: pairs must be an array.")

    errors: list[str] = []
    tag_ids: set[str] = set()
    if schema_version == 2:
        tag_ids = _validate_tag_definitions(data, errors)

    exact_seen: dict[tuple[str, str], int] = {}
    en_seen: dict[str, tuple[int, str]] = {}
    zh_seen: dict[str, tuple[int, str]] = {}

    for index, row in enumerate(pairs, start=1):
        if not isinstance(row, dict):
            errors.append(f"pairs[{index}] must be an object")
            continue

        if schema_version == 1:
            category = row.get("category")
            if category is not None and category not in LEGACY_TRANSLATION_CATEGORIES:
                errors.append(
                    f"pairs[{index}] has unsupported category: {category!r}"
                )
        else:
            row_tags = row.get("tags")
            if not isinstance(row_tags, list) or not row_tags:
                errors.append(f"pairs[{index}].tags must be a nonempty array")
            else:
                seen_tags: set[str] = set()
                for tag in row_tags:
                    tag = str(tag or "").strip()
                    if not tag:
                        errors.append(f"pairs[{index}].tags contains a blank tag")
                    elif tag not in tag_ids:
                        errors.append(f"pairs[{index}] uses unknown tag: {tag!r}")
                    elif tag in seen_tags:
                        errors.append(f"pairs[{index}] repeats tag: {tag!r}")
                    seen_tags.add(tag)

        en = str(row.get("en") or "").strip()
        zh = str(row.get("zh") or "").strip()
        if not en or not zh:
            errors.append(f"pairs[{index}] must contain both nonblank en and zh values")
            continue

        en_key = normalize_translation(en)
        zh_key = normalize_translation(zh)
        exact = (en_key, zh_key)

        if exact in exact_seen:
            errors.append(
                f"pairs[{index}] duplicates pairs[{exact_seen[exact]}]: {en} / {zh}"
            )
        else:
            exact_seen[exact] = index

        if en_key in en_seen and en_seen[en_key][1] != zh_key:
            errors.append(
                f"pairs[{index}] conflicts with pairs[{en_seen[en_key][0]}]: "
                f"English '{en}' maps to two Chinese values"
            )
        else:
            en_seen.setdefault(en_key, (index, zh_key))

        if zh_key in zh_seen and zh_seen[zh_key][1] != en_key:
            errors.append(
                f"pairs[{index}] conflicts with pairs[{zh_seen[zh_key][0]}]: "
                f"Chinese '{zh}' maps to two English values"
            )
        else:
            zh_seen.setdefault(zh_key, (index, en_key))

    if errors:
        raise ValueError("\n".join(errors))
    return pairs
