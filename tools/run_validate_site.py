#!/usr/bin/env python3
"""Run the current validator with safe root-relative website URL support."""
from __future__ import annotations

import re
import runpy
import urllib.parse
from pathlib import Path

import cms_extensions
cms_extensions.install()

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "validate_site.py"
_original_urlparse = urllib.parse.urlparse


def _safe_root_relative(value: object) -> bool:
    text = str(value or "").strip()
    return bool(
        text.startswith("/")
        and not text.startswith("//")
        and not any(char.isspace() for char in text)
        and "\\" not in text
        and not re.search(r"(?:^|/)\.\.(?:/|$)", text)
    )


def _urlparse(url, scheme="", allow_fragments=True):
    if _safe_root_relative(url):
        return _original_urlparse(
            "https://internal-path.invalid" + str(url),
            scheme=scheme,
            allow_fragments=allow_fragments,
        )
    return _original_urlparse(url, scheme=scheme, allow_fragments=allow_fragments)


urllib.parse.urlparse = _urlparse
runpy.run_path(str(SOURCE), run_name="__main__")
