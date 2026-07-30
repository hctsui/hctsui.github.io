from __future__ import annotations

import copy
from datetime import date
from typing import Any

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
    return items[: config["limit"]]


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
    return items[: config["limit"]]
