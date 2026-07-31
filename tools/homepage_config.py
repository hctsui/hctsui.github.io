from __future__ import annotations

import copy
from datetime import date
from typing import Any

from people_config import link_people_html, load_people

MAX_HOMEPAGE_ITEMS = 50
PUBLICATION_MODES = {"latest", "oldest", "manual"}
ACTIVITY_MODES = {"soonest", "farthest", "manual"}


def _positive_limit(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = fallback
    return min(MAX_HOMEPAGE_ITEMS, max(1, number))


def _unique_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for raw in value:
        item_id = str(raw or "").strip()
        if item_id and item_id not in result:
            result.append(item_id)
    return result


def _legacy_activity_ids(data: dict[str, Any]) -> list[str]:
    marked = [item for item in data.get("activities", []) if item.get("show_upcoming")]
    marked.sort(key=lambda item: (str(item.get("start_date") or ""), str(item.get("id") or "")))
    return [str(item["id"]) for item in marked if item.get("id")]


def default_homepage_config(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings", {})
    activity_ids = _legacy_activity_ids(data)
    return {
        "publications": {
            "mode": "latest",
            "limit": _positive_limit(settings.get("homepage_publication_limit", 2), 2),
            "selected_ids": [],
        },
        "activities": {
            "mode": "manual",
            "limit": max(1, len(activity_ids)),
            "selected_ids": activity_ids,
        },
    }


def normalized_homepage_config(
    data: dict[str, Any], value: Any | None = None
) -> dict[str, Any]:
    defaults = default_homepage_config(data)
    raw = value if value is not None else data.get("settings", {}).get("homepage")
    if not isinstance(raw, dict):
        return defaults
    publications = raw.get("publications")
    activities = raw.get("activities")
    publications = publications if isinstance(publications, dict) else {}
    activities = activities if isinstance(activities, dict) else {}
    publication_mode = str(publications.get("mode") or defaults["publications"]["mode"])
    activity_mode = str(activities.get("mode") or defaults["activities"]["mode"])
    if publication_mode not in PUBLICATION_MODES:
        publication_mode = defaults["publications"]["mode"]
    if activity_mode not in ACTIVITY_MODES:
        activity_mode = defaults["activities"]["mode"]
    return {
        "publications": {
            "mode": publication_mode,
            "limit": _positive_limit(publications.get("limit"), defaults["publications"]["limit"]),
            "selected_ids": _unique_ids(publications.get("selected_ids")),
        },
        "activities": {
            "mode": activity_mode,
            "limit": _positive_limit(activities.get("limit"), defaults["activities"]["limit"]),
            "selected_ids": _unique_ids(activities.get("selected_ids")),
        },
    }


def validate_homepage_config(data: dict[str, Any], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Homepage settings must be an object.")
    for section in ("publications", "activities"):
        if not isinstance(value.get(section), dict):
            raise ValueError(f"Homepage {section} settings must be an object.")
        raw_limit = value[section].get("limit")
        if isinstance(raw_limit, bool):
            raise ValueError(f"Homepage {section} limit must be an integer.")
        try:
            parsed_limit = int(raw_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Homepage {section} limit must be an integer.") from exc
        if parsed_limit < 1 or parsed_limit > MAX_HOMEPAGE_ITEMS:
            raise ValueError(f"Homepage {section} limit must be between 1 and {MAX_HOMEPAGE_ITEMS}.")
        selected = value[section].get("selected_ids")
        if not isinstance(selected, list) or any(
            not isinstance(item_id, str) or not item_id.strip() for item_id in selected
        ):
            raise ValueError(f"Homepage {section} selection must contain valid string IDs.")
        canonical_ids = [item_id.strip() for item_id in selected]
        if len(canonical_ids) != len(set(canonical_ids)):
            raise ValueError(f"Homepage {section} selection must contain unique IDs.")
    if value["publications"].get("mode") not in PUBLICATION_MODES:
        raise ValueError("Unsupported homepage publication mode.")
    if value["activities"].get("mode") not in ACTIVITY_MODES:
        raise ValueError("Unsupported homepage activity mode.")
    publication_ids = {str(item.get("id")) for item in data.get("publications", [])}
    activity_ids = {str(item.get("id")) for item in data.get("activities", [])}
    missing_publications = [item_id for item_id in value["publications"]["selected_ids"] if item_id not in publication_ids]
    missing_activities = [item_id for item_id in value["activities"]["selected_ids"] if item_id not in activity_ids]
    if missing_publications:
        raise ValueError("Homepage publication selection refers to missing entries: " + ", ".join(missing_publications[:5]))
    if missing_activities:
        raise ValueError("Homepage activity selection refers to missing entries: " + ", ".join(missing_activities[:5]))
    return normalized_homepage_config(data, value)


def apply_homepage_config(data: dict[str, Any], value: Any) -> dict[str, Any]:
    normalized = validate_homepage_config(data, value)
    settings = data.setdefault("settings", {})
    settings["homepage"] = copy.deepcopy(normalized)
    settings["homepage_publication_limit"] = normalized["publications"]["limit"]
    return normalized


def _active_activity(item: dict[str, Any], today: date) -> bool:
    final_date = str(item.get("end_date") or item.get("start_date") or "")
    return bool(final_date and final_date >= today.isoformat())


def _preferred_order(items: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    """Keep the selected set, but apply an optional user-defined relative order."""
    by_id = {str(item.get("id")): item for item in items}
    preferred = [by_id[item_id] for item_id in selected_ids if item_id in by_id]
    preferred_ids = {str(item.get("id")) for item in preferred}
    return preferred + [item for item in items if str(item.get("id")) not in preferred_ids]


def homepage_publications(data: dict[str, Any]) -> list[dict[str, Any]]:
    config = normalized_homepage_config(data)["publications"]
    items = list(data.get("publications", []))
    by_id = {str(item.get("id")): item for item in items}
    if config["mode"] == "manual":
        return [by_id[item_id] for item_id in config["selected_ids"] if item_id in by_id]
    items.sort(
        key=lambda item: (str(item.get("date") or ""), str(item.get("id") or "")),
        reverse=config["mode"] == "latest",
    )
    selected = items[: config["limit"]]
    return _preferred_order(selected, config["selected_ids"])


def homepage_activities(data: dict[str, Any], today: date) -> list[dict[str, Any]]:
    config = normalized_homepage_config(data)["activities"]
    items = [item for item in data.get("activities", []) if _active_activity(item, today)]
    by_id = {str(item.get("id")): item for item in items}
    if config["mode"] == "manual":
        return [by_id[item_id] for item_id in config["selected_ids"] if item_id in by_id]
    items.sort(
        key=lambda item: (str(item.get("start_date") or ""), str(item.get("id") or "")),
        reverse=config["mode"] == "farthest",
    )
    selected = items[: config["limit"]]
    return _preferred_order(selected, config["selected_ids"])


# ---------------------------------------------------------------------------
# Managed homepage hero/profile
# ---------------------------------------------------------------------------
# The Admin stores these settings as one internal generic record.  Assigning it
# to the derived home-publications category keeps it out of ordinary website and
# CV category rendering while letting the existing batch/content pipeline keep
# conflict checks, history, and undo support.
HOME_PROFILE_ITEM_ID = "home-profile-settings"
HOME_PROFILE_CATEGORY_ID = "home-publications"
HOME_PROFILE_MAX_ACTIONS = 12


def default_home_profile() -> dict[str, Any]:
    return {
        "kicker": {
            "en": "Department of Mathematics · National Tsing Hua University",
            "zh": "國立清華大學數學系",
        },
        "name_en": "Hung-Chun Tsui",
        "name_zh": "崔鴻竣",
        "role": {
            "en": "PhD student in mathematics",
            "zh": "數學系博士生",
        },
        "description": {
            "en": "Advisor: Professor Chieh-Yu Chang",
            "zh": "指導教授：張介玉教授",
        },
        # The optional link is kept for backward compatibility with the
        # existing advisor line, but the editable field is now generic.
        "description_url": "https://sites.google.com/gapp.nthu.edu.tw/cychang/",
        "description_link_text": {
            "en": "Chieh-Yu Chang",
            "zh": "張介玉教授",
        },
        "actions": [
            {"label": {"en": "CV", "zh": "履歷"}, "url": "cv.html"},
            {
                "label": {"en": "ORCID", "zh": "ORCID"},
                "url": "https://orcid.org/0009-0009-7445-5634",
            },
            {
                "label": {"en": "Email", "zh": "電子郵件"},
                "url": "mailto:hctsui@gapp.nthu.edu.tw",
            },
        ],
    }


def _profile_pair(value: Any, fallback: dict[str, str]) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    return {
        lang: str(source.get(lang) or fallback.get(lang) or "").strip()
        for lang in ("en", "zh")
    }


def _safe_home_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text or any(ord(ch) < 32 for ch in text) or any(ch.isspace() for ch in text):
        return ""
    lowered = text.casefold()
    if lowered.startswith(("javascript:", "data:", "vbscript:")):
        return ""
    if re.match(r"^[a-z][a-z0-9+.-]*:", text, flags=re.I):
        if lowered.startswith(("http://", "https://")):
            return text
        if lowered.startswith("mailto:") and "@" in text[7:]:
            return text
        return ""
    if text.startswith("//"):
        return ""
    return text


def normalized_home_profile(value: Any = None) -> dict[str, Any]:
    defaults = default_home_profile()
    raw = value if isinstance(value, dict) else {}
    actions: list[dict[str, Any]] = []
    for item in raw.get("actions", defaults["actions"]):
        if not isinstance(item, dict) or len(actions) >= HOME_PROFILE_MAX_ACTIONS:
            continue
        label = _profile_pair(item.get("label"), {"en": "", "zh": ""})
        url = _safe_home_url(item.get("url"))
        if label["en"] and label["zh"] and url:
            actions.append({"label": label, "url": url})
    return {
        "kicker": _profile_pair(raw.get("kicker"), defaults["kicker"]),
        "name_en": str(raw.get("name_en") or defaults["name_en"]).strip(),
        "name_zh": str(raw.get("name_zh") or defaults["name_zh"]).strip(),
        "role": _profile_pair(raw.get("role"), defaults["role"]),
        # Read the old advisor keys so existing saved data migrates without
        # losing text or links. New writes use the generic description keys.
        "description": _profile_pair(
            raw.get("description") or raw.get("advisor"), defaults["description"]
        ),
        "description_url": _safe_home_url(
            raw.get("description_url") or raw.get("advisor_url")
        ) or defaults["description_url"],
        "description_link_text": _profile_pair(
            raw.get("description_link_text") or raw.get("advisor_link_text"),
            defaults["description_link_text"],
        ),
        "actions": actions,
    }


def homepage_profile_record(data: dict[str, Any]) -> dict[str, Any] | None:
    for item in data.get("profile_items", []):
        if isinstance(item, dict) and str(item.get("id")) == HOME_PROFILE_ITEM_ID:
            return item
    return None


def homepage_profile(data: dict[str, Any]) -> dict[str, Any]:
    record = homepage_profile_record(data)
    return normalized_home_profile(record.get("profile") if record else None)


def _home_description_html(profile: dict[str, Any], lang: str) -> str:
    text = str(profile["description"].get(lang) or "")
    link_text = str(profile["description_link_text"].get(lang) or "")
    url = _safe_home_url(profile.get("description_url"))
    if url and link_text and link_text in text:
        before, after = text.split(link_text, 1)
        attrs = ' rel="noopener" target="_blank"' if url.startswith(("http://", "https://")) else ""
        fragment = (
            html.escape(before)
            + f'<a href="{html.escape(url, quote=True)}"{attrs}>'
            + html.escape(link_text)
            + "</a>"
            + html.escape(after)
        )
    else:
        fragment = html.escape(text)
    return link_people_html(fragment, load_people(), lang)


def _home_actions_html(profile: dict[str, Any], lang: str) -> str:
    links: list[str] = []
    for action in profile.get("actions", []):
        label = str((action.get("label") or {}).get(lang) or "").strip()
        url = _safe_home_url(action.get("url"))
        if not label or not url:
            continue
        attrs = ' rel="noopener" target="_blank"' if url.startswith(("http://", "https://")) else ""
        links.append(
            f'<a href="{html.escape(url, quote=True)}"{attrs}>{html.escape(label)}</a>'
        )
    return '<div class="home-actions">' + "".join(links) + "</div>"


def render_home_profile_hero(data: dict[str, Any], lang: str) -> str:
    profile = homepage_profile(data)
    kicker = html.escape(profile["kicker"][lang])
    role = html.escape(profile["role"][lang])
    name_en = html.escape(profile["name_en"])
    name_zh = html.escape(profile["name_zh"])
    description = _home_description_html(profile, lang)
    actions = _home_actions_html(profile, lang)
    if lang == "zh":
        photo = (
            '<div class="home-visual"><div class="home-visual-panel">'
            '<figure class="home-portrait"><img alt="風景照片" '
            'data-photo-candidates="../assets/images/photo-960.webp|../assets/images/photo.jpg" '
            'decoding="async" fetchpriority="high" height="720" '
            'sizes="(max-width: 800px) 100vw, 45vw" '
            'src="../assets/images/photo-960.webp" '
            'srcset="../assets/images/photo-640.webp 640w, ../assets/images/photo-960.webp 960w, ../assets/images/photo-1440.webp 1440w" '
            'width="960"/><figcaption>日本福岡志賀島，2025 年 9 月</figcaption>'
            '</figure></div></div>'
        )
    else:
        photo = (
            '<div class="home-visual"><div class="home-visual-panel">'
            '<figure class="home-portrait"><img alt="Landscape photograph" '
            'data-photo-candidates="assets/images/photo-960.webp|assets/images/photo.jpg" '
            'decoding="async" fetchpriority="high" height="720" '
            'sizes="(max-width: 800px) 100vw, 45vw" '
            'src="assets/images/photo-960.webp" '
            'srcset="assets/images/photo-640.webp 640w, assets/images/photo-960.webp 960w, assets/images/photo-1440.webp 1440w" '
            'width="960"/><figcaption>Shikanoshima, Fukuoka · September 2025</figcaption>'
            '</figure></div></div>'
        )
    return (
        '<section class="home-hero" id="top"><div class="container home-hero-grid">'
        '<div class="home-hero-copy">'
        f'<p class="home-kicker">{kicker}</p>'
        f'<h1 class="home-name">{name_en}<span class="home-name-zh">{name_zh}</span></h1>'
        f'<p class="home-role">{role}</p>'
        f'<p class="home-advisor">{description}</p>'
        f'{actions}</div>{photo}</div></section>'
    )


def replace_home_profile_hero(text: str, hero: str) -> str:
    updated, count = re.subn(
        r'<section class="home-hero"[^>]*>.*?</section>', hero, text, count=1, flags=re.S
    )
    if count != 1:
        raise RuntimeError("Could not find homepage hero section")
    return updated


def render_home_profile_files() -> None:
    root = Path(__file__).resolve().parents[1]
    data_file = root / "content" / "site.json"
    if not data_file.exists():
        return
    data = json.loads(data_file.read_text(encoding="utf-8"))
    for lang, relative in (("en", "index.html"), ("zh", "zh/index.html")):
        path = root / relative
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = replace_home_profile_hero(old, render_home_profile_hero(data, lang))
        if new != old:
            path.write_text(new, encoding="utf-8")


def _register_home_profile_post_build() -> None:
    # build_site.py imports homepage_config.  Registering this post-build step
    # keeps every existing workflow unchanged while ensuring the generated hero
    # comes from managed data rather than whichever HTML happened to exist.
    if Path(sys.argv[0]).name == "build_site.py":
        atexit.register(render_home_profile_files)


# Imports are intentionally local to the managed-home extension so the original
# homepage selection API remains unchanged.
import atexit  # noqa: E402
import html  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

_register_home_profile_post_build()
