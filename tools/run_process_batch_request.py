#!/usr/bin/env python3
"""Run the current batch processor with profile, Dossier and placement support."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cms_extensions as ext

ext.install()
import category_config as categories
import process_batch_request as batch


def stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


_original_layout_bundle = batch.layout_bundle
_original_normalized_layout_bundle = batch.normalized_layout_bundle
_original_apply_layout_bundle = batch.apply_layout_bundle
_original_layout_structure = batch.layout_structure
_original_apply_special = batch.apply_special
_original_apply_undo = batch.apply_undo


def virtual_page_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": ext.PDF_CV_PAGE_ID,
            "name": {"en": "PDF CV", "zh": "PDF 履歷"},
            "path": {"en": "", "zh": ""},
            "languages": ["en", "zh"],
            "header": None,
            "color": "#735748",
            "show_in_navigation": False,
            "order": 9000,
            "virtual": True,
            "virtual_kind": "pdf_cv",
        },
        {
            "id": ext.PERSONAL_PAGE_ID,
            "name": {"en": "Personal Information", "zh": "個人資料"},
            "path": {"en": "", "zh": ""},
            "languages": ["en", "zh"],
            "header": None,
            "color": "#675c83",
            "show_in_navigation": False,
            "order": 9001,
            "virtual": True,
            "virtual_kind": "personal_profile",
        },
    ]


def with_virtual_pages(value: Any) -> list[dict[str, Any]]:
    rows = [copy.deepcopy(row) for row in value if isinstance(row, dict) and str(row.get("id") or "") not in ext.VIRTUAL_PAGE_IDS] if isinstance(value, list) else []
    rows.extend(virtual_page_rows())
    return rows


def public_pages(value: Any) -> list[dict[str, Any]]:
    return [copy.deepcopy(row) for row in value if isinstance(row, dict) and str(row.get("id") or "") not in ext.VIRTUAL_PAGE_IDS] if isinstance(value, list) else []


def placements_from_data(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    known = {row["id"] for row in categories.normalized_categories(data)}
    result = {}
    for item in categories.all_items(data):
        iid = str(item.get("id") or "")
        if not iid:
            continue
        result[iid] = ext.normalize_placements(
            item.get("display_placements"),
            primary=str(item.get("category_id") or ""),
            known=known,
        )
    return result


def layout_bundle(data: dict[str, Any]) -> dict[str, Any]:
    ext.ensure_special_categories(data)
    result = _original_layout_bundle(data)
    result["pages"] = with_virtual_pages(result.get("pages", []))
    result["categories"] = copy.deepcopy(categories.normalized_categories(data))
    result["cv_category_order"] = copy.deepcopy(categories.normalized_cv_order(data))
    result["dossier_category_order"] = copy.deepcopy(ext.normalized_dossier_order(data))
    result["placements"] = placements_from_data(data)
    return result


def normalized_layout_bundle(data: dict[str, Any], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Layout operation requires an object.")
    standard = {
        "pages": with_virtual_pages(value.get("pages", [])),
        "categories": copy.deepcopy(value.get("categories", [])),
        "cv_category_order": copy.deepcopy(value.get("cv_category_order", [])),
        "assignments": copy.deepcopy(value.get("assignments", {})),
    }
    result = _original_normalized_layout_bundle(data, standard)
    category_rows = result.get("categories", [])
    known = {str(row.get("id") or "") for row in category_rows}
    eligible = {
        str(row.get("id") or "") for row in category_rows
        if row.get("id") != ext.PROFILE_CATEGORY_ID
        and row.get("kind") not in {"featured_publications", "upcoming", "contact"}
    }
    raw_order = value.get("dossier_category_order", [])
    if not isinstance(raw_order, list):
        raise ValueError("dossier_category_order must be an array.")
    result["dossier_category_order"] = list(dict.fromkeys(str(cid) for cid in raw_order if str(cid) in eligible))

    raw_placements = value.get("placements", {})
    if not isinstance(raw_placements, dict):
        raise ValueError("Layout placements must be an object.")
    assignments = result.get("assignments", {})
    if set(raw_placements) - set(assignments):
        raise ValueError("Layout placements contain unknown item IDs; reload Admin.")
    result["placements"] = {
        iid: ext.normalize_placements(
            raw_placements.get(iid, []),
            primary=str((assignments.get(iid) or {}).get("category_id") or ""),
            known=known,
        )
        for iid in assignments
    }
    return result


def apply_layout_bundle(data: dict[str, Any], value: Any) -> dict[str, Any]:
    normalized = normalized_layout_bundle(data, value)
    standard = {key: copy.deepcopy(normalized[key]) for key in ("pages", "categories", "cv_category_order", "assignments")}
    _original_apply_layout_bundle(data, standard)
    settings = data.setdefault("settings", {})
    settings["pages"] = public_pages(settings.get("pages", []))
    settings["categories"] = copy.deepcopy(categories.normalized_categories(data))
    settings["cv_category_order"] = copy.deepcopy(categories.normalized_cv_order(data))
    settings["dossier_category_order"] = copy.deepcopy(normalized["dossier_category_order"])
    by_id = {str(item.get("id") or ""): item for item in categories.all_items(data)}
    for iid, rows in normalized["placements"].items():
        if iid in by_id:
            by_id[iid]["display_placements"] = copy.deepcopy(rows)
    ext.sync_personal_profile(data)
    return layout_bundle(data)


def layout_structure(value: Any) -> dict[str, Any]:
    result = _original_layout_structure(value)
    if not isinstance(value, dict):
        result.update(dossier_category_order=[], placements={})
        return result
    result["dossier_category_order"] = copy.deepcopy(value.get("dossier_category_order", []))
    result["placements"] = copy.deepcopy(value.get("placements", {}))
    return result


batch.layout_bundle = layout_bundle
batch.normalized_layout_bundle = normalized_layout_bundle
batch.apply_layout_bundle = apply_layout_bundle
batch.layout_structure = layout_structure


def apply_special(data, trans, history, op, hid, issue, applied_at, request_digest, *args, **kwargs):
    if op.get("op") != "personal_profile":
        return _original_apply_special(data, trans, history, op, hid, issue, applied_at, request_digest, *args, **kwargs)
    before = ext.personal_profile(data)
    expected = op.get("before")
    if expected is not None and stable(ext.normalize_profile(expected, data)) != stable(before):
        raise ValueError("Conflict: personal profile changed after Admin loaded.")
    after = ext.sync_personal_profile(data, op.get("after"))
    batch.append_history(
        history,
        history_id=hid,
        issue_number=issue,
        applied_at=applied_at,
        request_digest=request_digest,
        request_action="personal_profile",
        action="personal_profile",
        type="personal_profile",
        entry_id="personal-profile",
        label={"en": "Personal profile", "zh": "個人資料"},
        before=copy.deepcopy(before),
        after=copy.deepcopy(after),
        index_before=None,
        index_after=None,
        undo_of=None,
    )
    return "personal_profile", "personal-profile"


batch.apply_special = apply_special


def apply_undo(data, trans, history, op, hid, issue, applied_at, request_digest, *args, **kwargs):
    target_id = op.get("history_id")
    target = next((row for row in history.get("operations", []) if row.get("history_id") == target_id), None)
    if not target or target.get("action") != "personal_profile":
        return _original_apply_undo(data, trans, history, op, hid, issue, applied_at, request_digest, *args, **kwargs)
    if target.get("reverted_by"):
        raise ValueError(f"{target_id} was already undone.")
    current = ext.personal_profile(data)
    if stable(current) != stable(ext.normalize_profile(target.get("after"), data)):
        raise ValueError("Cannot undo personal profile: it changed later.")
    restored = ext.sync_personal_profile(data, target.get("before"))
    new = batch.append_history(
        history,
        history_id=hid,
        issue_number=issue,
        applied_at=applied_at,
        request_digest=request_digest,
        request_action="undo",
        action="personal_profile",
        type="personal_profile",
        entry_id="personal-profile",
        label=target.get("label") or {"en": "Personal profile", "zh": "個人資料"},
        before=copy.deepcopy(current),
        after=copy.deepcopy(restored),
        index_before=None,
        index_after=None,
        undo_of=target_id,
    )
    target["reverted_by"] = new["history_id"]
    return "undo", "personal-profile"


batch.apply_undo = apply_undo

if __name__ == "__main__":
    batch.main()
