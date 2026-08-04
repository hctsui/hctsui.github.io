#!/usr/bin/env python3
"""Protect complete external media URLs from legacy local-path rewrites."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

_ABSOLUTE_URL = re.compile(r"https?://[^\s\"'<>]+", flags=re.I)


def apply_static_asset_paths_safely(
    original: Callable[[str, str], str],
    text: str,
    lang: str,
) -> str:
    """Run the existing local migration without touching complete HTTP(S) URLs."""
    protected: dict[str, str] = {}

    def stash(match: re.Match[str]) -> str:
        token = f"__HCTSUI_ABSOLUTE_MEDIA_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    result = original(_ABSOLUTE_URL.sub(stash, text), lang)
    for token, url in protected.items():
        result = result.replace(token, url)
    return result


def patch_build_site(module: Any) -> None:
    """Patch build_site once; all other rendering behavior remains unchanged."""
    if getattr(module, "_r2_absolute_media_urls_patched", False):
        return

    original = module.apply_static_asset_paths

    def apply_static_asset_paths(text: str, lang: str) -> str:
        return apply_static_asset_paths_safely(original, text, lang)

    module.apply_static_asset_paths = apply_static_asset_paths
    module._r2_absolute_media_urls_patched = True
