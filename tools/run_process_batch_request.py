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

# These pages exist only to make the Admin UI easier to navigate. They are not
# ordinary persisted CMS pages and therefore must not participate in stale-data
# conflicts or be written back to content/site.json.
DOSSIER_PAGE_ID = "dossier"
SYNTHETIC_LAYOUT_PAGE_IDS = set(ext.VIRTUAL_PAGE_IDS) | {DOSSIER_PAGE_ID}


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
    rows = [
        copy.deepcopy(row)
        for row in value
        if isinstance(row, dict)
        and str(row.get("id") or "") not in ext.VIRTUAL_PAGE_IDS
    ] if isinstance(value, list) else []
    rows.extend(virtual_page_rows())
    return rows


def public_pages(value: Any) -> list[dict[str, Any]]:
    """Return only real CMS pages.

    In particular, the browser-only Dossier row must never leak into site.json.
    """
    return [
        copy.deepcopy(row)
        for row in value
        if isinstance(row, dict)
        and str(row.get("id") or "") not in SYNTHETIC_LAYOUT_PAGE_IDS
    ] if isinstance(value, list) else []


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

    # Older/racing Admin state may not yet contain the Dossier extension fields.
    # Missing fields mean "leave the current value alone", never "clear it".
    if "dossier_category_order" in value:
        raw_order = value.get("dossier_category_order", [])
        if not isinstance(raw_order, list):
            raise ValueError("dossier_category_order must be an array.")
        result["dossier_category_order"] = list(
            dict.fromkeys(str(cid) for cid in raw_order if str(cid) in eligible)
        )
    else:
        result["dossier_category_order"] = copy.deepcopy(
            ext.normalized_dossier_order(data)
        )

    assignments = result.get("assignments", {})
    if "placements" in value:
        raw_placements = value.get("placements", {})
        if not isinstance(raw_placements, dict):
            raise ValueError("Layout placements must be an object.")
        if set(raw_placements) - set(assignments):
            raise ValueError("Layout placements contain unknown item IDs; reload Admin.")
    else:
        raw_placements = placements_from_data(data)

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
    standard = {
        key: copy.deepcopy(normalized[key])
        for key in ("pages", "categories", "cv_category_order", "assignments")
    }
    _original_apply_layout_bundle(data, standard)
    settings = data.setdefault("settings", {})
    settings["pages"] = public_pages(settings.get("pages", []))
    settings["categories"] = copy.deepcopy(categories.normalized_categories(data))
    settings["cv_category_order"] = copy.deepcopy(categories.normalized_cv_order(data))
    settings["dossier_category_order"] = copy.deepcopy(
        normalized["dossier_category_order"]
    )
    by_id = {
        str(item.get("id") or ""): item
        for item in categories.all_items(data)
    }
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
    result["dossier_category_order"] = copy.deepcopy(
        value.get("dossier_category_order", [])
    )
    result["placements"] = copy.deepcopy(value.get("placements", {}))
    return result


def _canonical_public_pages(value: Any) -> list[dict[str, Any]]:
    rows = public_pages(value)
    rows.sort(
        key=lambda row: (
            int(row.get("order", 0) or 0),
            str(row.get("id") or ""),
        )
    )
    # admin/layout.js rewrites visible page order to 0,1,2,...
    for index, row in enumerate(rows):
        row["order"] = index
    return rows


def _canonical_categories(value: Any) -> list[dict[str, Any]]:
    """Match admin/layout.js category normalization exactly enough for conflicts.

    In particular, category order is *relative to its page*.  A legacy stored
    order such as cv-personal.order == 3 is therefore equivalent to order == 0
    when it is the only category on the PDF-CV virtual page.
    """
    rows = [copy.deepcopy(row) for row in value if isinstance(row, dict)] if isinstance(value, list) else []
    rows.sort(
        key=lambda row: (
            str(row.get("page_id") or ""),
            int(row.get("order", 0) or 0),
            str(row.get("id") or ""),
        )
    )
    counters: dict[str, int] = {}
    for row in rows:
        page_id = str(row.get("page_id") or "")
        row["order"] = counters.get(page_id, 0)
        counters[page_id] = row["order"] + 1
        for field in ("label", "title", "intro"):
            pair = row.get(field) if isinstance(row.get(field), dict) else {}
            row[field] = {
                "en": str(pair.get("en") or ""),
                "zh": str(pair.get("zh") or ""),
            }
        row["show_on_web"] = row.get("show_on_web") is not False
        row["show_on_cv"] = bool(row.get("show_on_cv"))
    return rows


def _canonical_assignment_and_placements(value: Any) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Mirror layout.js + dossier-category.js order normalization.

    Frontend layout state uses contiguous order numbers.  The persistent data
    may contain legacy/gapped numbers, so comparing raw integers creates false
    stale-layout conflicts even when the visible order is identical.
    """
    source = value if isinstance(value, dict) else {}
    raw_assignments = source.get("assignments", {}) if isinstance(source.get("assignments"), dict) else {}
    assignments: dict[str, dict[str, Any]] = {}
    for iid, state in raw_assignments.items():
        state = state if isinstance(state, dict) else {}
        try:
            order = int(state.get("order", 999999))
        except (TypeError, ValueError):
            order = 999999
        assignments[str(iid)] = {
            "category_id": str(state.get("category_id") or ""),
            "order": order,
        }

    # First pass from admin/layout.js: primary items are contiguous per category.
    by_category: dict[str, list[str]] = {}
    for iid, state in assignments.items():
        by_category.setdefault(state["category_id"], []).append(iid)
    for ids in by_category.values():
        ids.sort(key=lambda iid: (assignments[iid]["order"], iid))
        for index, iid in enumerate(ids):
            assignments[iid]["order"] = index

    known_categories = {
        str(row.get("id") or "")
        for row in source.get("categories", [])
        if isinstance(row, dict) and row.get("id")
    }
    raw_placements = source.get("placements", {}) if isinstance(source.get("placements"), dict) else {}
    placements: dict[str, list[dict[str, Any]]] = {}
    for iid in assignments:
        primary = assignments[iid]["category_id"]
        rows = raw_placements.get(iid, []) if isinstance(raw_placements.get(iid, []), list) else []
        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            category_id = str(row.get("category_id") or "")
            if (
                not category_id
                or category_id == primary
                or category_id in seen
                or (known_categories and category_id not in known_categories)
            ):
                continue
            seen.add(category_id)
            try:
                order = int(row.get("order", index))
            except (TypeError, ValueError):
                order = index
            normalized.append({"category_id": category_id, "order": order})
        placements[iid] = normalized

    # dossier-category.js then merges primary + placement references per category
    # and gives the whole visible list one contiguous ordering.
    category_ids = set(known_categories)
    category_ids.update(state["category_id"] for state in assignments.values())
    category_ids.update(
        row["category_id"] for rows in placements.values() for row in rows
    )
    for category_id in category_ids:
        refs: list[tuple[int, str, str]] = []
        for iid, state in assignments.items():
            if state["category_id"] == category_id:
                refs.append((state["order"], iid, "primary"))
        for iid, rows in placements.items():
            for row in rows:
                if row["category_id"] == category_id:
                    refs.append((row["order"], iid, "placement"))
        refs.sort(key=lambda ref: (ref[0], ref[1]))
        for index, (_, iid, kind) in enumerate(refs):
            if kind == "primary":
                assignments[iid]["order"] = index
            else:
                row = next(
                    row for row in placements[iid]
                    if row["category_id"] == category_id
                )
                row["order"] = index

    for rows in placements.values():
        rows.sort(key=lambda row: (row["category_id"], row["order"]))
    return assignments, placements


def _canonical_layout(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    assignments, placements = _canonical_assignment_and_placements(source)
    return {
        "pages": _canonical_public_pages(source.get("pages", [])),
        "categories": _canonical_categories(source.get("categories", [])),
        "cv_category_order": copy.deepcopy(source.get("cv_category_order", [])),
        "assignments": assignments,
        "placements": placements,
        "dossier_category_order": copy.deepcopy(source.get("dossier_category_order", [])),
    }


def _same_shared_mapping(
    current: dict[str, Any],
    expected: dict[str, Any],
    key: str,
) -> bool:
    left = current.get(key, {}) if isinstance(current.get(key), dict) else {}
    right = expected.get(key, {}) if isinstance(expected.get(key), dict) else {}
    for iid in set(left) & set(right):
        if stable(left[iid]) != stable(right[iid]):
            return False
    return True


def layout_expected_matches(current: Any, expected: Any) -> bool:
    """Detect genuine stale edits without rejecting equivalent normalized layouts."""
    if not isinstance(expected, dict):
        return True
    left = _canonical_layout(current)
    right = _canonical_layout(expected)

    for key in ("pages", "categories", "cv_category_order"):
        if stable(left[key]) != stable(right[key]):
            return False

    # Add/delete may have run earlier in this same batch; only IDs that existed
    # in both snapshots can represent a stale concurrent edit.
    if not _same_shared_mapping(left, right, "assignments"):
        return False
    if "placements" in expected and not _same_shared_mapping(left, right, "placements"):
        return False
    if "dossier_category_order" in expected:
        if stable(left["dossier_category_order"]) != stable(right["dossier_category_order"]):
            return False
    return True


def layout_after_already_applied(current: Any, requested: Any) -> bool:
    """Return True only when the requested layout is already the current layout.

    This safely handles content-only edits that caused Admin to emit an auxiliary
    layout operation.  It is not a blanket conflict bypass: real requested layout
    changes still go through the normal stale-state check and apply path.
    """
    if not isinstance(requested, dict):
        return False
    left = _canonical_layout(current)
    right = _canonical_layout(requested)
    for key in ("pages", "categories", "cv_category_order"):
        if stable(left[key]) != stable(right[key]):
            return False
    if not _same_shared_mapping(left, right, "assignments"):
        return False
    # If requested mentions every current assignment, equality on the shared set
    # means the primary layout state is already fully applied.
    if set(right["assignments"]) != set(left["assignments"]):
        return False
    if "placements" in requested:
        if stable(left["placements"]) != stable(right["placements"]):
            return False
    if "dossier_category_order" in requested:
        if stable(left["dossier_category_order"]) != stable(right["dossier_category_order"]):
            return False
    return True

batch.layout_bundle = layout_bundle
batch.normalized_layout_bundle = normalized_layout_bundle
batch.apply_layout_bundle = apply_layout_bundle
batch.layout_structure = layout_structure
batch.layout_expected_matches = layout_expected_matches


def apply_special(
    data,
    trans,
    history,
    op,
    hid,
    issue,
    applied_at,
    request_digest,
    *args,
    **kwargs,
):
    if op.get("op") == "layout":
        current = layout_bundle(data)
        if layout_after_already_applied(current, op.get("after")):
            batch.append_history(
                history,
                history_id=hid,
                issue_number=issue,
                applied_at=applied_at,
                request_digest=request_digest,
                request_action="layout",
                action="layout",
                type="layout",
                entry_id="layout",
                label={"en": "Page and category layout", "zh": "頁面與類別"},
                before=copy.deepcopy(current),
                after=copy.deepcopy(current),
                index_before=None,
                index_after=None,
                undo_of=None,
            )
            return "layout", "layout"
        return _original_apply_special(
            data, trans, history, op, hid, issue, applied_at, request_digest, *args, **kwargs
        )
    if op.get("op") != "personal_profile":
        return _original_apply_special(
            data,
            trans,
            history,
            op,
            hid,
            issue,
            applied_at,
            request_digest,
            *args,
            **kwargs,
        )
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


def apply_undo(
    data,
    trans,
    history,
    op,
    hid,
    issue,
    applied_at,
    request_digest,
    *args,
    **kwargs,
):
    target_id = op.get("history_id")
    target = next(
        (
            row
            for row in history.get("operations", [])
            if row.get("history_id") == target_id
        ),
        None,
    )
    if not target or target.get("action") != "personal_profile":
        return _original_apply_undo(
            data,
            trans,
            history,
            op,
            hid,
            issue,
            applied_at,
            request_digest,
            *args,
            **kwargs,
        )
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
