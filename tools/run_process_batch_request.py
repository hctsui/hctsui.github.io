#!/usr/bin/env python3
"""Run the current batch processor with profile, Dossier and placement support."""
from __future__ import annotations

import argparse
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
_original_validate_operation = batch.validate_operation
_original_main = batch.main

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


def _assignment_category_map(layout: dict[str, Any]) -> dict[str, str]:
    assignments = layout.get("assignments", {}) if isinstance(layout.get("assignments"), dict) else {}
    return {
        str(iid): str((state if isinstance(state, dict) else {}).get("category_id") or "")
        for iid, state in assignments.items()
    }


def _placement_category_map(layout: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    placements = layout.get("placements", {}) if isinstance(layout.get("placements"), dict) else {}
    result: dict[str, tuple[str, ...]] = {}
    for iid, rows in placements.items():
        values = []
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("category_id"):
                values.append(str(row["category_id"]))
        result[str(iid)] = tuple(sorted(dict.fromkeys(values)))
    return result


def _visible_sequences(
    layout: dict[str, Any],
    ids: set[str],
    *,
    include_placements: bool,
) -> dict[str, list[tuple[str, str]]]:
    """Return relative per-category display order for the selected item IDs.

    Numeric order values are deliberately discarded after sorting.  This makes
    stale checks invariant under unrelated items added/deleted in between two
    shared items while still detecting a real relative reorder.
    """
    refs: dict[str, list[tuple[int, str, str]]] = {}
    assignments = layout.get("assignments", {}) if isinstance(layout.get("assignments"), dict) else {}
    for iid in ids:
        state = assignments.get(iid)
        if not isinstance(state, dict):
            continue
        category_id = str(state.get("category_id") or "")
        try:
            order = int(state.get("order", 999999))
        except (TypeError, ValueError):
            order = 999999
        refs.setdefault(category_id, []).append((order, iid, "primary"))
    if include_placements:
        placements = layout.get("placements", {}) if isinstance(layout.get("placements"), dict) else {}
        for iid in ids:
            rows = placements.get(iid, [])
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                category_id = str(row.get("category_id") or "")
                if not category_id:
                    continue
                try:
                    order = int(row.get("order", 999999))
                except (TypeError, ValueError):
                    order = 999999
                refs.setdefault(category_id, []).append((order, iid, "placement"))
    return {
        category_id: [(iid, kind) for _, iid, kind in sorted(rows, key=lambda x: (x[0], x[1], x[2]))]
        for category_id, rows in refs.items()
    }


def _shared_item_state_matches(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    include_placements: bool,
) -> bool:
    left_assignments = left.get("assignments", {}) if isinstance(left.get("assignments"), dict) else {}
    right_assignments = right.get("assignments", {}) if isinstance(right.get("assignments"), dict) else {}
    shared = set(left_assignments) & set(right_assignments)
    left_categories = _assignment_category_map(left)
    right_categories = _assignment_category_map(right)
    for iid in shared:
        if left_categories.get(iid) != right_categories.get(iid):
            return False
    if include_placements:
        left_placements = _placement_category_map(left)
        right_placements = _placement_category_map(right)
        for iid in shared:
            if left_placements.get(iid, ()) != right_placements.get(iid, ()):
                return False
    return _visible_sequences(left, shared, include_placements=include_placements) == _visible_sequences(
        right, shared, include_placements=include_placements
    )


def layout_expected_matches(current: Any, expected: Any) -> bool:
    """Detect genuine stale layout edits while ignoring unrelated item churn."""
    if not isinstance(expected, dict):
        return True
    left = _canonical_layout(current)
    right = _canonical_layout(expected)

    for key in ("pages", "categories", "cv_category_order"):
        if stable(left[key]) != stable(right[key]):
            return False

    if not _shared_item_state_matches(
        left,
        right,
        include_placements="placements" in expected,
    ):
        return False
    if "dossier_category_order" in expected:
        if stable(left["dossier_category_order"]) != stable(right["dossier_category_order"]):
            return False
    return True


def _layout_refs(layout: dict[str, Any], category_id: str) -> list[tuple[str, str]]:
    refs: list[tuple[int, str, str]] = []
    assignments = layout.get("assignments", {}) if isinstance(layout.get("assignments"), dict) else {}
    for iid, state in assignments.items():
        if not isinstance(state, dict) or str(state.get("category_id") or "") != category_id:
            continue
        try:
            order = int(state.get("order", 999999))
        except (TypeError, ValueError):
            order = 999999
        refs.append((order, str(iid), "primary"))
    placements = layout.get("placements", {}) if isinstance(layout.get("placements"), dict) else {}
    for iid, rows in placements.items():
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict) or str(row.get("category_id") or "") != category_id:
                continue
            try:
                order = int(row.get("order", 999999))
            except (TypeError, ValueError):
                order = 999999
            refs.append((order, str(iid), "placement"))
    return [(iid, kind) for _, iid, kind in sorted(refs, key=lambda x: (x[0], x[1], x[2]))]


def _rebase_reference_order(
    current: dict[str, Any],
    requested: dict[str, Any],
    assignments: dict[str, dict[str, Any]],
    placements: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Apply requested relative order while retaining current-only references.

    Unknown/current-only references keep their current slots whenever possible;
    requested references occupy the remaining slots in the submitted relative
    order.  This is the layout analogue of process_batch_request.merge_sequence.
    """
    final_layout = {"assignments": assignments, "placements": placements}
    category_ids = {str(state.get("category_id") or "") for state in assignments.values()}
    category_ids.update(
        str(row.get("category_id") or "")
        for rows in placements.values()
        for row in rows
        if isinstance(row, dict)
    )
    for category_id in category_ids:
        final_set = set(_layout_refs(final_layout, category_id))
        current_sequence = [ref for ref in _layout_refs(current, category_id) if ref in final_set]
        requested_sequence = [ref for ref in _layout_refs(requested, category_id) if ref in final_set]
        base = list(current_sequence)
        seen = set(base)
        # Moved-in/new references are appended before the requested sequence is
        # overlaid, so they can still move ahead of known references as requested.
        for ref in requested_sequence:
            if ref not in seen:
                base.append(ref)
                seen.add(ref)
        for ref in sorted(final_set):
            if ref not in seen:
                base.append(ref)
                seen.add(ref)
        wanted = set(requested_sequence)
        slots = [index for index, ref in enumerate(base) if ref in wanted]
        if len(slots) != len(requested_sequence):
            raise ValueError("Could not rebase page/category item ordering safely; reload Admin.")
        for index, ref in zip(slots, requested_sequence):
            base[index] = ref
        for order, (iid, kind) in enumerate(base):
            if kind == "primary":
                assignments[iid]["order"] = order
            else:
                row = next(
                    row for row in placements.get(iid, [])
                    if str(row.get("category_id") or "") == category_id
                )
                row["order"] = order
    for rows in placements.values():
        rows.sort(key=lambda row: (str(row.get("category_id") or ""), int(row.get("order", 999999))))
    return assignments, placements


def rebase_layout_bundle(current: Any, requested: Any) -> dict[str, Any]:
    """Rebase a submitted layout onto the current set of content items.

    * current-only IDs are preserved;
    * IDs that no longer exist are dropped;
    * requested changes for still-existing IDs are applied;
    * deleting a category that gained an unseen item/reference is rejected.
    """
    if not isinstance(requested, dict):
        raise ValueError("Layout operation requires an object.")
    current_canonical = _canonical_layout(current)
    requested_canonical = _canonical_layout(requested)
    current_assignments = current_canonical["assignments"]
    requested_assignments = requested_canonical["assignments"]
    known_categories = {
        str(row.get("id") or "")
        for row in requested_canonical["categories"]
        if isinstance(row, dict) and row.get("id")
    }

    current_only = set(current_assignments) - set(requested_assignments)
    for iid in current_only:
        category_id = str((current_assignments[iid] or {}).get("category_id") or "")
        if category_id and category_id not in known_categories:
            raise ValueError(
                f"Layout category {category_id} gained item {iid} after Admin loaded; reload Admin before deleting it."
            )
        for row in current_canonical["placements"].get(iid, []):
            placement_category = str(row.get("category_id") or "")
            if placement_category and placement_category not in known_categories:
                raise ValueError(
                    f"Layout category {placement_category} gained a reference after Admin loaded; reload Admin before deleting it."
                )

    assignments: dict[str, dict[str, Any]] = {}
    for iid, current_state in current_assignments.items():
        state = requested_assignments.get(iid, current_state)
        assignments[iid] = copy.deepcopy(state)

    current_placements = current_canonical["placements"]
    requested_has_placements = "placements" in requested
    requested_placements = requested_canonical["placements"] if requested_has_placements else {}
    placements: dict[str, list[dict[str, Any]]] = {}
    for iid in current_assignments:
        if requested_has_placements and iid in requested_assignments:
            placements[iid] = copy.deepcopy(requested_placements.get(iid, []))
        else:
            placements[iid] = copy.deepcopy(current_placements.get(iid, []))

    assignments, placements = _rebase_reference_order(
        current_canonical,
        requested_canonical,
        assignments,
        placements,
    )

    result = {
        "pages": copy.deepcopy(requested.get("pages", [])),
        "categories": copy.deepcopy(requested.get("categories", [])),
        "cv_category_order": copy.deepcopy(requested.get("cv_category_order", [])),
        "assignments": assignments,
        "placements": placements,
    }
    if "dossier_category_order" in requested:
        result["dossier_category_order"] = copy.deepcopy(requested.get("dossier_category_order", []))
    else:
        result["dossier_category_order"] = copy.deepcopy(current_canonical["dossier_category_order"])
    return result

batch.layout_bundle = layout_bundle
batch.normalized_layout_bundle = normalized_layout_bundle
batch.apply_layout_bundle = apply_layout_bundle
batch.layout_structure = layout_structure
batch.layout_expected_matches = layout_expected_matches


def validate_operation(op: Any) -> None:
    if isinstance(op, dict) and op.get("op") == "personal_profile":
        if not isinstance(op.get("before"), dict) or not isinstance(op.get("after"), dict):
            raise ValueError("Personal profile operation requires before and after objects.")
        return
    _original_validate_operation(op)


batch.validate_operation = validate_operation


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
        before = layout_bundle(data)
        expected = op.get("before")
        if expected is not None and not layout_expected_matches(before, expected):
            raise ValueError("Conflict: page/category layout changed after Admin loaded.")
        rebased = rebase_layout_bundle(before, op.get("after"))
        after = apply_layout_bundle(data, rebased)
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
            before=copy.deepcopy(before),
            after=copy.deepcopy(after),
            index_before=None,
            index_after=None,
            undo_of=None,
        )
        return "layout", "layout"
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
    if not target or target.get("action") not in {"personal_profile", "layout"}:
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
    if target.get("expires_at") and batch.dt(target["expires_at"]) <= applied_at:
        raise ValueError(f"Undo expired: {target_id}")

    if target.get("action") == "layout":
        current = layout_bundle(data)
        if not layout_expected_matches(current, target.get("after")):
            raise ValueError("Cannot undo layout: layout changed later.")
        rebased = rebase_layout_bundle(current, target.get("before"))
        restored = apply_layout_bundle(data, rebased)
        new = batch.append_history(
            history,
            history_id=hid,
            issue_number=issue,
            applied_at=applied_at,
            request_digest=request_digest,
            request_action="undo",
            action="layout",
            type="layout",
            entry_id="layout",
            label=target.get("label") or {"en": "Page and category layout", "zh": "頁面與類別"},
            before=copy.deepcopy(current),
            after=copy.deepcopy(restored),
            index_before=None,
            index_after=None,
            undo_of=target_id,
        )
        target["reverted_by"] = new["history_id"]
        return "undo", "layout"

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


def _extended_main() -> None:
    """Run the batch loop when an extension-only operation needs explicit routing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("event")
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args()
    event = json.load(open(args.event, encoding="utf-8"))
    issue = int(event["issue"]["number"])
    payload = batch.parse_body(event["issue"]["body"])
    operations = payload.get("operations", [])
    if payload.get("schema_version") != 2 or not isinstance(operations, list):
        raise ValueError("Invalid batch payload.")

    data = batch.migrate_category_data(json.load(open(batch.SITE, encoding="utf-8")))
    translations = json.load(open(batch.TRANS, encoding="utf-8"))
    batch.normalize_translation_tags(translations)
    people = batch.normalized_people(
        json.load(open(batch.PEOPLE, encoding="utf-8")) if batch.PEOPLE.exists() else batch.empty_people()
    )
    batch.validate_people(people)
    arxiv_store = batch.normalized_arxiv_store(
        json.load(open(batch.ARXIV_STORE, encoding="utf-8")) if batch.ARXIV_STORE.exists() else batch.empty_arxiv_store()
    )
    batch.validate_arxiv_store(arxiv_store)
    notifications = batch.normalized_notification_store(
        json.load(open(batch.NOTIFICATIONS, encoding="utf-8")) if batch.NOTIFICATIONS.exists() else batch.empty_notification_store()
    )
    batch.validate_notification_store(notifications)
    history = batch.load_history()
    applied_at = batch.now()
    batch.prune(history, applied_at)
    existing = {row["history_id"]: row for row in history["operations"]}
    action_names = (
        "add", "update", "delete", "undo", "reorder", "translations", "people",
        "arxiv_suggestions", "notifications", "site_settings", "headings", "layout",
        "homepage", "personal_profile", "replayed",
    )
    counts = {name: 0 for name in action_names}
    ids: list[str] = []
    special = {
        "reorder", "translations", "people", "arxiv_suggestions", "notifications",
        "site_settings", "headings", "layout", "homepage", "personal_profile",
    }

    for index, op in enumerate(operations, 1):
        batch.validate_operation(op)
        history_id = f"issue-{issue}-op-{index}"
        request_digest = batch.digest(op)
        if history_id in existing:
            if existing[history_id].get("request_digest") != request_digest:
                raise ValueError(f"{history_id} exists with different content.")
            counts["replayed"] += 1
            continue
        if op["op"] == "undo":
            action, entry_id = batch.apply_undo(
                data, translations, history, op, history_id, issue, applied_at, request_digest,
                people=people, arxiv_store=arxiv_store, notifications=notifications,
            )
        elif op["op"] in special:
            action, entry_id = batch.apply_special(
                data, translations, history, op, history_id, issue, applied_at, request_digest,
                people=people, arxiv_store=arxiv_store, notifications=notifications,
            )
        else:
            action, entry_id = batch.apply_content(
                data, history, op, history_id, issue, applied_at, request_digest
            )
        counts[action] += 1
        ids.append(entry_id)
        existing[history_id] = history["operations"][-1]

    batch.normalize_groups(data)
    data = batch.strip_invisible_chars(batch.migrate_category_data(data))
    translations = batch.strip_invisible_chars(translations)
    people = batch.strip_invisible_chars(batch.normalized_people(people))
    arxiv_store = batch.strip_invisible_chars(batch.normalized_arxiv_store(arxiv_store))
    notifications = batch.strip_invisible_chars(batch.normalized_notification_store(notifications))
    history = batch.strip_invisible_chars(history)
    batch.validate_category_data(data)
    batch.validate_homepage_config(data, batch.normalized_homepage_config(data))
    batch.validate_trans(translations)
    batch.validate_people(people)
    batch.validate_arxiv_store(arxiv_store)
    batch.validate_notification_store(notifications)
    batch.validate_site_settings(batch.current_site_settings(data), data)

    batch.SITE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch.TRANS.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch.PEOPLE.write_text(json.dumps(people, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch.ARXIV_STORE.write_text(json.dumps(arxiv_store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch.NOTIFICATIONS.write_text(json.dumps(notifications, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    batch.HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_keys = (
        "add", "update", "delete", "undo", "reorder", "translations", "people",
        "arxiv_suggestions", "notifications", "site_settings", "headings", "layout",
        "homepage", "personal_profile",
    )
    summary = "批次完成：" + "、".join(
        f"{key} {counts[key]}" for key in summary_keys if counts[key]
    )
    result = {
        "action": summary or "沒有新操作",
        "entry_id": ", ".join(ids[:8]),
        "notes": ["每筆操作已保存七天，可在 Admin 單筆 Undo。"],
        "warnings": [],
    }
    Path(args.result_file).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    # Keep the core processor's exact main loop for ordinary batches. Only the
    # personal-profile extension needs the slightly wider action/count routing.
    use_extended = False
    if len(sys.argv) > 1:
        try:
            event = json.load(open(sys.argv[1], encoding="utf-8"))
            payload = batch.parse_body(event["issue"]["body"])
            use_extended = any(
                isinstance(op, dict) and op.get("op") == "personal_profile"
                for op in payload.get("operations", [])
            )
        except Exception:
            # Let the core parser produce the canonical error for malformed input.
            use_extended = False
    if use_extended:
        _extended_main()
    else:
        _original_main()


if __name__ == "__main__":
    main()
