#!/usr/bin/env python3
"""Validate the explicit bidirectional translation dictionary."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "content" / "translations.json"


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", text).strip().casefold()


def main() -> None:
    if not PATH.exists():
        raise SystemExit("Missing content/translations.json")
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"content/translations.json is invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("content/translations.json must contain a JSON object.")
    if data.get("schema_version") != 1:
        raise SystemExit("content/translations.json: schema_version must be 1.")
    pairs = data.get("pairs")
    if not isinstance(pairs, list):
        raise SystemExit("content/translations.json: pairs must be an array.")

    errors: list[str] = []
    en_seen: dict[str, tuple[int, str]] = {}
    zh_seen: dict[str, tuple[int, str]] = {}
    exact_seen: set[tuple[str, str]] = set()

    for index, row in enumerate(pairs, start=1):
        if not isinstance(row, dict):
            errors.append(f"pairs[{index}] must be an object")
            continue
        en = str(row.get("en") or "").strip()
        zh = str(row.get("zh") or "").strip()
        if not en or not zh:
            errors.append(f"pairs[{index}] must contain both nonblank en and zh values")
            continue
        en_key, zh_key = normalize(en), normalize(zh)
        exact = (en_key, zh_key)
        if exact in exact_seen:
            errors.append(f"pairs[{index}] duplicates an earlier pair: {en} / {zh}")
        exact_seen.add(exact)

        if en_key in en_seen and en_seen[en_key][1] != zh:
            errors.append(
                f"pairs[{index}] conflicts with pairs[{en_seen[en_key][0]}]: "
                f"English '{en}' maps to two Chinese values"
            )
        else:
            en_seen[en_key] = (index, zh)

        if zh_key in zh_seen and zh_seen[zh_key][1] != en:
            errors.append(
                f"pairs[{index}] conflicts with pairs[{zh_seen[zh_key][0]}]: "
                f"Chinese '{zh}' maps to two English values"
            )
        else:
            zh_seen[zh_key] = (index, en)

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Validated {len(pairs)} explicit bilingual pairs.")


if __name__ == "__main__":
    main()
