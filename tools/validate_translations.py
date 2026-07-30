#!/usr/bin/env python3
"""Validate the explicit bilingual dictionary using the shared rules."""
from __future__ import annotations

import json
from pathlib import Path

from translation_validation import validate_translation_data

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "content" / "translations.json"


def main() -> None:
    if not PATH.exists():
        raise SystemExit("Missing content/translations.json")
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
        pairs = validate_translation_data(data)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"content/translations.json is invalid JSON: {exc}") from exc
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Validated {len(pairs)} explicit bilingual pairs.")


if __name__ == "__main__":
    main()
