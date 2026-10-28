"""Additive CMS extension for scheduled updates and public activity visibility.

No content is deleted or reclassified. It changes only website/CV rendering,
search-index data, and the site-settings save/undo layer.
"""
from __future__ import annotations

import copy
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_SCHEDULE = {"enabled": True, "time": "00:15", "timezone": "Asia/Tokyo"}
ACTIVITY_TYPES = {"visit", "talk", "conference", "organization"}
_INSTALLED = False


def normalize_schedule(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    time = str(source.get("time", DEFAULT_SCHEDULE["time"])).strip()
    timezone = str(source.get("timezone", DEFAULT_SCHEDULE["timezone"])).strip()
    enabled = source.get("enabled", DEFAULT_SCHEDULE["enabled"])
    if not isinstance(enabled, bool):
        raise ValueError("Daily automatic update enabled must be boolean")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
        raise ValueError("Daily automatic update time must be HH:MM")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ValueError(f"Unknown daily automatic update time zone: {timezone}") from exc
    return {"enabled": enabled, "time": time, "timezone": timezone}


def schedule_from_data(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings") or {}
    # Existing setting remains the fallback for users who have not edited this.
    legacy_timezone = settings.get("timezone") or DEFAULT_SCHEDULE["timezone"]
    raw = settings.get("auto_update")
    if not isinstance(raw, dict):
        raw = {**DEFAULT_SCHEDULE, "timezone": legacy_timezone}
    return normalize_schedule(raw)


def activity_finished(item: dict[str, Any], today: date) -> bool:
    if str(item.get("type") or "") not in ACTIVITY_TYPES:
        return True
    end = str(item.get("end_date") or item.get("start_date") or "").strip()
    if not end:
        return True  # Legacy undated entries remain visible rather than lost.
    try:
        return date.fromisoformat(end) < today
    except ValueError:
        return True


def local_today(data: dict[str, Any]) -> date:
    override = os.environ.get("SITE_TODAY")
    if override:
        return date.fromisoformat(override)
    return datetime.now(ZoneInfo(schedule_from_data(data)["timezone"])).date()


def _install_settings() -> None:
    import site_settings_config as config
    import process_batch_request as batch

    old_normalize = config.normalized_site_settings
    old_current = config.current_site_settings
    old_validate = config.validate_site_settings

    def normalized(value: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
        result = old_normalize(value, data)
        raw = value.get("auto_update") if isinstance(value, dict) else None
        if raw is None and data is not None:
            raw = schedule_from_data(data)
        result["auto_update"] = normalize_schedule(raw)
        return result

    def current(data: dict[str, Any]) -> dict[str, Any]:
        value = old_current(data)
        value["auto_update"] = schedule_from_data(data)
        return value

    def validate(value: Any, data: dict[str, Any] | None = None) -> Any:
        original = old_validate(value, data)
        normalize_schedule(value.get("auto_update") if isinstance(value, dict) else None)
        return original

    config.normalized_site_settings = normalized
    config.current_site_settings = current
    config.validate_site_settings = validate
    # The batch processor used named imports before this module was initialized.
    batch.normalized_site_settings = normalized
    batch.current_site_settings = current
    batch.validate_site_settings = validate

    old_special = batch.apply_special
    old_undo = batch.apply_undo

    def persist_latest_after(data: dict[str, Any], history: dict[str, Any]) -> None:
        rows = history.get("operations") or []
        after = rows[-1].get("after") if rows else None
        if not isinstance(after, dict) or "auto_update" not in after:
            raise RuntimeError("Batch processor did not retain the schedule update")
        setting = normalize_schedule(after["auto_update"])
        data.setdefault("settings", {})["auto_update"] = copy.deepcopy(setting)
        # Keep site_today() and the schedule in the same IANA timezone.
        data["settings"]["timezone"] = setting["timezone"]

    def apply_special(data, translations, history, op, *args, **kwargs):
        result = old_special(data, translations, history, op, *args, **kwargs)
        if op.get("op") == "site_settings":
            persist_latest_after(data, history)
        return result

    def apply_undo(data, translations, history, op, *args, **kwargs):
        result = old_undo(data, translations, history, op, *args, **kwargs)
        last = (history.get("operations") or [{}])[-1]
        if result[0] == "undo" and last.get("action") == "site_settings":
            persist_latest_after(data, history)
        return result

    batch.apply_special = apply_special
    batch.apply_undo = apply_undo


def _install_visibility() -> None:
    import r2_build_fix as renderfix
    old_clean = renderfix.clean_generated_activity_pages

    def filter_activity(module, data, category, today, items):
        if str(category.get("kind") or "") == "upcoming":
            return items
        return [item for item in items if activity_finished(item, today)]

    def clean_pages(module, data, today):
        paths = old_clean(module, data, today)
        root = Path(module.ROOT)
        hidden_ids = {
            str(row.get("id")) for row in data.get("activities", [])
            if row.get("id") and not activity_finished(row, today)
        }
        for rel in ("activities.html", "zh/activities.html"):
            path = root / rel
            if not path.is_file():
                continue
            original = path.read_text(encoding="utf-8")
            text = original
            for item_id in sorted(hidden_ids):
                for rendered_id in renderfix._article_markers(text, item_id):
                    text = renderfix._remove_article(text, rendered_id)
            if any(renderfix._article_markers(text, item_id) for item_id in hidden_ids):
                raise RuntimeError(f"Unfinished activities still present in {rel}")
            if text != original:
                path.write_text(text, encoding="utf-8")
                if path not in paths:
                    paths.append(path)
        return paths

    renderfix.filter_upcoming_from_activities = filter_activity
    renderfix.clean_generated_activity_pages = clean_pages


def _install_dossier_visibility() -> None:
    # build_dossier.py does `from category_config import items_for_category`.
    # Patch only within that command; other CMS/admin data remains unfiltered.
    import category_config
    original = category_config.items_for_category

    def completed_only(data, category_id):
        today = local_today(data)
        return [row for row in original(data, category_id) if activity_finished(row, today)]

    category_config.items_for_category = completed_only


def _install_search_visibility() -> None:
    # The index reads all content directly. Do not index hidden future records
    # (even though they remain editable in content/site.json / Admin).
    import process_request as core
    original = core.migrate_data

    def public_only(data):
        result = original(data)
        public = copy.deepcopy(result)
        today = local_today(public)
        public["activities"] = [row for row in public.get("activities", []) if activity_finished(row, today)]
        return public

    core.migrate_data = public_only


def _install_admin_script() -> None:
    # All existing deploy workflows run Python before publishing admin/index.html.
    # Insert the separate UI module without replacing the 160-kB admin index.
    root = Path(__file__).resolve().parents[1]
    page = root / "admin/index.html"
    if not page.is_file():
        return
    raw = page.read_text(encoding="utf-8")
    script = '<script src="auto-update.js?v=20261028-1"></script>'
    if script in raw:
        return
    marker = '<script src="github-submit.js'
    pos = raw.find(marker)
    if pos == -1:
        raise RuntimeError("Cannot inject daily-update Admin JS: GitHub submit script missing")
    raw = raw[:pos] + script + "\n    " + raw[pos:]
    page.write_text(raw, encoding="utf-8")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_settings()
    _install_visibility()
    name = Path(sys.argv[0]).name
    if name == "build_dossier.py":
        _install_dossier_visibility()
    if name == "build_search_index.py":
        _install_search_visibility()
    if (Path(__file__).resolve().parents[1] / "admin/index.html").is_file():
        _install_admin_script()
