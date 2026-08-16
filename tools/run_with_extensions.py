#!/usr/bin/env python3
"""Run one existing tool with the non-destructive CMS schema extensions loaded."""
from __future__ import annotations

import argparse
import atexit
import html
import importlib
import json
import re
import runpy
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cms_extensions
import r2_build_fix


# ---------------------------------------------------------------------------
# Homepage search-identity post-build fix
# ---------------------------------------------------------------------------
# IMPORTANT:
# - SEO/OG/canonical/hreflang/sitemap remain owned by build_site.py + the CMS.
# - This post-build layer only:
#     (1) makes the localized name the primary visible H1 on each homepage;
#     (2) injects ProfilePage/Person JSON-LD for identity disambiguation.
# - The managed marker makes the injection idempotent.
_PROFILE_IDENTITY_START = "<!-- managed:profile-search-identity -->"
_PROFILE_IDENTITY_END = "<!-- /managed:profile-search-identity -->"


def _canonical_home_urls(data: dict) -> dict[str, str]:
    """Read homepage URLs from the CMS settings without changing any SEO fields."""
    from category_config import normalized_pages
    from site_settings_config import current_site_settings

    seo = current_site_settings(data)["seo"]
    base = str(seo["base_url"]).rstrip("/") + "/"
    home = next(
        (page for page in normalized_pages(data) if str(page.get("id") or "") == "home"),
        None,
    )
    paths = (home or {}).get("path") or {}

    def canonical(lang: str, fallback: str) -> str:
        rel = str(paths.get(lang) or fallback)
        # Match build_site.py's canonical convention: index.html -> directory URL.
        if rel.endswith("index.html"):
            rel = rel[:-10]
        return urljoin(base, rel)

    return {
        "en": canonical("en", "index.html"),
        "zh": canonical("zh", "zh/index.html"),
    }


def _profile_same_as(profile: dict) -> list[str]:
    """Collect identity-profile URLs only; do not treat arbitrary homepage buttons as sameAs."""
    result: list[str] = []
    for action in profile.get("actions", []):
        if not isinstance(action, dict):
            continue
        url = str(action.get("url") or "").strip()
        labels = action.get("label") or {}
        label_text = " ".join(str(labels.get(lang) or "") for lang in ("en", "zh")).casefold()

        # ORCID is currently the verified identity profile exposed on the homepage.
        # More identity providers can be added here later without touching CMS SEO/OG.
        if url.startswith(("https://", "http://")) and (
            "orcid" in label_text or "orcid.org/" in url.casefold()
        ):
            if url not in result:
                result.append(url)
    return result


def _json_for_script(payload: dict) -> str:
    """Serialize JSON-LD safely inside an HTML <script> element."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
    )


def _profile_json_ld(profile: dict, lang: str, page_url: str, english_url: str) -> str:
    name_en = str(profile.get("name_en") or "Hung-Chun Tsui").strip()
    name_zh = str(profile.get("name_zh") or "崔鴻竣").strip()
    name_en_unhyphenated = re.sub(r"(?<=\w)-(?=\w)", " ", name_en)

    if lang == "zh":
        primary_name = name_zh
        alternate_names = [name_en, name_en_unhyphenated]
        language = "zh-Hant"
    else:
        primary_name = name_en
        alternate_names = [name_en_unhyphenated, name_zh]
        language = "en"

    # Keep order stable while dropping duplicates/blanks.
    alternate_names = [
        value
        for index, value in enumerate(alternate_names)
        if value and value != primary_name and value not in alternate_names[:index]
    ]

    person = {
        "@type": "Person",
        "@id": english_url + "#person",
        "name": primary_name,
        "alternateName": alternate_names,
        # One stable identity URL for the Person entity; the ProfilePage itself
        # remains language-specific through its own url/inLanguage.
        "url": english_url,
    }
    same_as = _profile_same_as(profile)
    if same_as:
        person["sameAs"] = same_as

    payload = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "@id": page_url + "#profile",
        "url": page_url,
        "inLanguage": language,
        "mainEntity": person,
    }
    return (
        _PROFILE_IDENTITY_START
        + '\n<script type="application/ld+json">'
        + _json_for_script(payload)
        + "</script>\n"
        + _PROFILE_IDENTITY_END
    )


def _replace_localized_home_h1(text: str, profile: dict, lang: str) -> str:
    name_en = html.escape(str(profile.get("name_en") or "Hung-Chun Tsui").strip())
    name_zh = html.escape(str(profile.get("name_zh") or "崔鴻竣").strip())

    if lang == "zh":
        primary = name_zh
        secondary = name_en
        secondary_lang = "en"
    else:
        primary = name_en
        secondary = name_zh
        secondary_lang = "zh-Hant"

    replacement = (
        f'<h1 class="home-name">{primary}'
        f'<span class="home-name-zh" lang="{secondary_lang}">{secondary}</span>'
        "</h1>"
    )

    pattern = (
        r'<h1\b(?=[^>]*\bclass=["\'][^"\']*\bhome-name\b[^"\']*["\'])'
        r"[^>]*>.*?</h1>"
    )
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.I)
    if count != 1:
        raise RuntimeError("Could not find localized homepage H1")
    return updated


def _inject_profile_json_ld(
    text: str, profile: dict, lang: str, page_url: str, english_url: str
) -> str:
    # Remove only this feature's own managed block. Existing CMS metadata,
    # Open Graph, Twitter cards, canonical and hreflang tags are untouched.
    pattern = (
        re.escape(_PROFILE_IDENTITY_START)
        + r".*?"
        + re.escape(_PROFILE_IDENTITY_END)
        + r"\s*"
    )
    text = re.sub(pattern, "", text, flags=re.S)

    block = _profile_json_ld(profile, lang, page_url, english_url)
    if "</head>" not in text:
        raise RuntimeError("Could not find </head> for ProfilePage JSON-LD")
    return text.replace("</head>", block + "\n</head>", 1)


def _apply_profile_search_identity() -> None:
    """Final post-build pass, intentionally after homepage_config's hero renderer."""
    data_file = ROOT / "content" / "site.json"
    if not data_file.exists():
        return

    from homepage_config import homepage_profile

    data = json.loads(data_file.read_text(encoding="utf-8"))
    profile = homepage_profile(data)
    urls = _canonical_home_urls(data)

    targets = (
        ("en", ROOT / "index.html"),
        ("zh", ROOT / "zh" / "index.html"),
    )
    for lang, path in targets:
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = _replace_localized_home_h1(old, profile, lang)
        new = _inject_profile_json_ld(new, profile, lang, urls[lang], urls["en"])
        if new != old:
            path.write_text(new, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    target = Path(options.target)
    if not target.is_absolute():
        target = ROOT / target
    if not target.exists():
        raise SystemExit(f"Tool not found: {target}")

    cms_extensions.install()
    sys.argv = [str(target), *options.args]
    if target.name == "build_site.py":
        # Register BEFORE importing build_site.py. homepage_config registers its
        # own atexit hero renderer during that import; atexit is LIFO, so the
        # existing hero renderer runs first and this identity pass runs last.
        atexit.register(_apply_profile_search_identity)

        module = importlib.import_module("build_site")
        cms_extensions.patch_build_site(module)
        r2_build_fix.patch_build_site(module)
        module.main()
        return
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
