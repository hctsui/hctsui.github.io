#!/usr/bin/env python3
"""Shared validation and normalization for the explicit bilingual dictionary."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def strip_limited_markup(value: str) -> str:
    return re.sub(r"\[/?(?:i|b)\]", "", value, flags=re.I).strip()


def normalize_translation(value: Any) -> str:
    text = unicodedata.normalize("NFKC", strip_limited_markup(str(value or "")))
    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_translation_data(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("content/translations.json must contain a JSON object.")
    if data.get("schema_version") != 1:
        raise ValueError("content/translations.json: schema_version must be 1.")
    pairs = data.get("pairs")
    if not isinstance(pairs, list):
        raise ValueError("content/translations.json: pairs must be an array.")

    errors: list[str] = []
    exact_seen: dict[tuple[str, str], int] = {}
    en_seen: dict[str, tuple[int, str]] = {}
    zh_seen: dict[str, tuple[int, str]] = {}

    for index, row in enumerate(pairs, start=1):
        if not isinstance(row, dict):
            errors.append(f"pairs[{index}] must be an object")
            continue

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
