#!/usr/bin/env python3
"""Dynamic-group website form processor.

Extends process_request_v3 with:
- publication sections (Journal Articles, Preprints, Survey Papers, custom);
- teaching sections grouped by institution;
- automatic publication reclassification after journal metadata is added;
- safe removal of empty custom groups;
- persistent manual ordering submitted from the Admin page.
"""

from __future__ import annotations

import json
import re
from typing import Any

import process_request_v3 as v3

base = v3.base

ORIGINAL_LOAD_DATA = base.load_data
ORIGINAL_ADD_PUBLICATION = base.add_publication
ORIGINAL_EDIT_ENTRY = base.edit_entry
ORIGINAL_REMOVE_ENTRY = base.remove_entry
ORIGINAL_PROCESS = base.process

base.FIELD_LABELS.update({
    "publication_group": "論文分類",
    "custom_group": "自訂大標題",
    "ordering": "排序資料",
})

PRESET_PUBLICATION_GROUPS = [
    {
        "id": "journal-articles",
        "label": {"en": "Journal Articles", "zh": "期刊論文"},
        "order": 0,
        "preset": True,
    },
    {
        "id": "preprints",
        "label": {"en": "Preprints", "zh": "預印本"},
        "order": 10,
        "preset": True,
    },
    {
        "id": "survey-papers",
        "label": {"en": "Survey Papers", "zh": "綜述論文"},
        "order": 20,
        "preset": True,
    },
]

DEFAULT_INSTITUTION = {"en": "National Tsing Hua University", "zh": "國立清華大學"}

GROUPED_KINDS = {"publication", "teaching"}
UNGROUPED_KINDS = {"conference", "talk", "visit", "honor"}
SORTABLE_KINDS = GROUPED_KINDS | UNGROUPED_KINDS


def entries_of_kind(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    if kind in {"conference", "talk", "visit"}:
        return [entry for entry in data.get("activities", []) if entry.get("type") == kind]
    if kind == "honor":
        return list(data.get("honors", []))
    if kind == "publication":
        return list(data.get("publications", []))
    if kind == "teaching":
        return list(data.get("teaching", []))
    raise ValueError(f"Unknown sortable kind: {kind}")


def default_ungrouped_ids(data: dict[str, Any], kind: str) -> list[str]:
    entries = entries_of_kind(data, kind)
    if kind == "honor":
        entries.sort(
            key=lambda entry: (
                -int(entry.get("year", 0)),
                int(entry.get("order", 999999)),
                str(entry.get("id", "")),
            )
        )
    else:
        entries.sort(
            key=lambda entry: (str(entry.get("start_date", "")), str(entry.get("id", ""))),
            reverse=True,
        )
    return [str(entry.get("id")) for entry in entries]


def entry_order_settings(data: dict[str, Any]) -> dict[str, list[str]]:
    settings = data.setdefault("settings", {})
    value = settings.setdefault("entry_order", {})
    if not isinstance(value, dict):
        value = {}
        settings["entry_order"] = value
    return value


def manually_ordered_kinds(data: dict[str, Any]) -> set[str]:
    settings = data.setdefault("settings", {})
    raw = settings.setdefault("manually_ordered_kinds", [])
    if not isinstance(raw, list):
        raw = []
        settings["manually_ordered_kinds"] = raw
    return {str(kind) for kind in raw}


def mark_manually_ordered(data: dict[str, Any], kind: str) -> None:
    settings = data.setdefault("settings", {})
    kinds = manually_ordered_kinds(data)
    kinds.add(kind)
    settings["manually_ordered_kinds"] = sorted(kinds)


def sync_ungrouped_order(data: dict[str, Any], kind: str) -> None:
    if kind not in UNGROUPED_KINDS:
        return
    order_map = entry_order_settings(data)
    current_ids = {str(entry.get("id")) for entry in entries_of_kind(data, kind)}
    defaults = [entry_id for entry_id in default_ungrouped_ids(data, kind) if entry_id in current_ids]
    if kind not in manually_ordered_kinds(data):
        order_map[kind] = defaults
        return
    previous = [str(entry_id) for entry_id in order_map.get(kind, []) if str(entry_id) in current_ids]
    missing = [entry_id for entry_id in defaults if entry_id not in previous]
    # A new item must never disturb an existing hand-made order. It is appended
    # and can then be moved from Admin whenever desired.
    order_map[kind] = previous + missing


def parse_ordering_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    # GitHub Issue Forms wrap textarea values in a fenced block whenever the
    # field has `render: json`. Accept both fenced and plain JSON so old open
    # Issues remain usable after this fix.
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ordering payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Ordering payload must be one JSON object.")
    return payload


def slugify(value: str) -> str:
    value = base.strip_markup(value).casefold().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if value:
        return value[:70]
    digest = base.hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"group-{digest}"


def content_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    settings = data.setdefault("settings", {})
    groups = settings.setdefault("content_groups", {})
    return groups.setdefault(kind, [])


def group_label(group: dict[str, Any], lang: str = "en") -> str:
    label = group.get("label") or {}
    if isinstance(label, dict):
        return str(label.get(lang) or label.get("en") or "")
    return str(label or "")


def ensure_group(
    data: dict[str, Any],
    kind: str,
    label: dict[str, str],
    *,
    group_id: str | None = None,
    preset: bool = False,
) -> dict[str, Any]:
    groups = content_groups(data, kind)
    wanted_id = group_id or slugify(label.get("en") or label.get("zh") or "group")
    for group in groups:
        if group.get("id") == wanted_id:
            group.setdefault("label", {}).update({k: v for k, v in label.items() if v})
            if preset:
                group["preset"] = True
            return group
        if group_label(group, "en").casefold() == label.get("en", "").casefold() and label.get("en"):
            return group
    order = max([int(g.get("order", -1)) for g in groups] + [-1]) + 1
    group = {
        "id": wanted_id,
        "label": {"en": label.get("en", ""), "zh": label.get("zh") or label.get("en", "")},
        "order": order,
    }
    if preset:
        group["preset"] = True
    groups.append(group)
    return group


def find_group(data: dict[str, Any], kind: str, group_id: str) -> dict[str, Any] | None:
    return next((g for g in content_groups(data, kind) if g.get("id") == group_id), None)


def normalize_orders(data: dict[str, Any], kind: str) -> None:
    groups = sorted(content_groups(data, kind), key=lambda g: (int(g.get("order", 999999)), str(g.get("id", ""))))
    for group_order, group in enumerate(groups):
        group["order"] = group_order
        section = "publications" if kind == "publication" else "teaching"
        entries = [e for e in data.get(section, []) if e.get("group_id") == group.get("id")]
        entries.sort(key=lambda e: (int(e.get("order", 999999)), str(e.get("id", ""))))
        for entry_order, entry in enumerate(entries):
            entry["order"] = entry_order


def publication_has_link(entry: dict[str, Any], label: str) -> bool:
    return any(
        str((link.get("label") or {}).get("en") or "").casefold() == label.casefold()
        and bool(link.get("url"))
        for link in entry.get("links", [])
    )


def publication_group_id(entry: dict[str, Any]) -> str:
    """Conservatively identify journal articles; otherwise use Preprints.

    Survey/custom categories are deliberately explicit choices, not AI guesses.
    """
    if publication_has_link(entry, "DOI") or publication_has_link(entry, "Journal"):
        return "journal-articles"
    venue_obj = entry.get("venue") or {}
    venue = str(venue_obj.get("en") if isinstance(venue_obj, dict) else venue_obj or "").strip()
    lowered = venue.casefold()
    if not lowered or lowered.startswith("arxiv:"):
        return "preprints"
    preprint_markers = (
        "submitted", "under review", "preprint", "in preparation", "manuscript",
        "投稿", "審查中", "準備中",
    )
    if any(marker in lowered for marker in preprint_markers):
        return "preprints"
    journal_markers = (
        "accepted", "to appear", "published", "forthcoming", "vol.", "volume ",
        "issue ", "no.", "journal", "proceedings", "communications", "transactions",
    )
    if any(marker in lowered for marker in journal_markers):
        return "journal-articles"
    # A non-status venue containing year/volume/page punctuation is likely a citation.
    if re.search(r"\b\d{1,4}\b.*(?:\(|\)|:|--|–)", venue):
        return "journal-articles"
    return "preprints"


def migrate_data(data: dict[str, Any]) -> dict[str, Any]:
    for preset in PRESET_PUBLICATION_GROUPS:
        ensure_group(
            data,
            "publication",
            dict(preset["label"]),
            group_id=str(preset["id"]),
            preset=True,
        )

    nthu = ensure_group(data, "teaching", DEFAULT_INSTITUTION, group_id="national-tsing-hua-university")

    for entry in data.get("publications", []):
        if not entry.get("group_id") or not find_group(data, "publication", str(entry.get("group_id"))):
            entry["group_id"] = publication_group_id(entry)

    for entry in data.get("teaching", []):
        institution = entry.get("institution")
        if not isinstance(institution, dict) or not (institution.get("en") or institution.get("zh")):
            institution = dict(DEFAULT_INSTITUTION)
        institution_en = str(institution.get("en") or institution.get("zh") or "Institution").strip()
        institution_zh = str(institution.get("zh") or institution.get("en") or "機構").strip()
        if institution_en.casefold() in {"nthu", "national tsing hua university"}:
            institution_en = DEFAULT_INSTITUTION["en"]
            institution_zh = DEFAULT_INSTITUTION["zh"]
        institution = {"en": institution_en, "zh": institution_zh}
        entry["institution"] = institution
        gid = slugify(institution_en)
        group = ensure_group(data, "teaching", institution, group_id=gid)
        entry["group_id"] = group["id"]
        entry.setdefault("role", dict(v3.DEFAULT_ROLE if hasattr(v3, "DEFAULT_ROLE") else {"en": "Teaching Assistant", "zh": "助教"}))

    normalize_orders(data, "publication")
    normalize_orders(data, "teaching")
    for kind in sorted(UNGROUPED_KINDS):
        sync_ungrouped_order(data, kind)
    return data


def load_data() -> dict[str, Any]:
    return migrate_data(ORIGINAL_LOAD_DATA())


def selected_group_id(value: str) -> str:
    match = re.search(r"\[([a-z0-9][a-z0-9-]*)\]\s*$", value.strip(), flags=re.I)
    return match.group(1).casefold() if match else ""


def translate_pair(data: dict[str, Any], kind: str, fields: dict[str, str], en: str, zh: str, key: str) -> dict[str, str]:
    if zh.strip():
        return {"en": en.strip(), "zh": zh.strip()}
    translated_fields = dict(fields)
    translated_fields["Chinese handling / 中文欄位處理"] = (
        "Auto translate blank Chinese fields / 自動翻譯空白中文欄位"
    )
    translated = base.fill_chinese(data, kind, translated_fields, {key: (en, "")})[key]
    return {"en": en.strip(), "zh": translated or en.strip()}


def resolve_custom_group(
    data: dict[str, Any],
    kind: str,
    fields: dict[str, str],
    en_label: str,
    zh_label: str,
) -> dict[str, Any]:
    en = base.get(fields, en_label, True)
    zh = base.get(fields, zh_label)
    label = translate_pair(data, kind, fields, en, zh, "custom_group")
    return ensure_group(data, kind, label)


def resolve_publication_group(
    data: dict[str, Any],
    fields: dict[str, str],
    entry: dict[str, Any],
    *,
    edit: bool = False,
    metadata_changed: bool = False,
) -> dict[str, Any]:
    label = "New publication section / 新論文大標題" if edit else "Publication section / 論文大標題"
    selected = base.get(fields, label).strip()
    lowered = selected.casefold()

    if edit and (not selected or lowered.startswith("keep unchanged") or lowered.startswith("維持不變")):
        if metadata_changed and publication_group_id(entry) == "journal-articles":
            return find_group(data, "publication", "journal-articles") or ensure_group(
                data, "publication", {"en": "Journal Articles", "zh": "期刊論文"},
                group_id="journal-articles", preset=True,
            )
        current = find_group(data, "publication", str(entry.get("group_id") or ""))
        if current:
            return current

    if not selected or lowered.startswith("auto") or "自動判斷" in selected:
        gid = publication_group_id(entry)
        return find_group(data, "publication", gid) or ensure_group(
            data, "publication", {"en": gid.replace("-", " ").title(), "zh": gid}, group_id=gid
        )

    if lowered.startswith("other") or "其他" in selected:
        return resolve_custom_group(
            data,
            "publication",
            fields,
            "New custom publication section (English) / 新自訂論文大標題英文" if edit
            else "Custom publication section (English) / 自訂論文大標題英文",
            "New custom publication section (Chinese) / 新自訂論文大標題中文" if edit
            else "Custom publication section (Chinese) / 自訂論文大標題中文",
        )

    gid = selected_group_id(selected)
    group = find_group(data, "publication", gid)
    if group:
        return group
    raise ValueError(f"Unknown publication section option: {selected}")


def resolve_teaching_group(
    data: dict[str, Any],
    fields: dict[str, str],
    *,
    edit: bool = False,
) -> dict[str, Any] | None:
    label = "New institution section / 新機構大標題" if edit else "Institution section / 機構大標題"
    selected = base.get(fields, label).strip()
    lowered = selected.casefold()
    if edit and (not selected or lowered.startswith("keep unchanged") or lowered.startswith("維持不變")):
        return None
    if lowered.startswith("other") or "其他" in selected:
        return resolve_custom_group(
            data,
            "teaching",
            fields,
            "New custom institution (English) / 新自訂機構英文" if edit
            else "Custom institution (English) / 自訂機構英文",
            "New custom institution (Chinese) / 新自訂機構中文" if edit
            else "Custom institution (Chinese) / 自訂機構中文",
        )
    gid = selected_group_id(selected)
    group = find_group(data, "teaching", gid)
    if group:
        return group
    raise ValueError(f"Unknown institution option: {selected}")


def next_order(data: dict[str, Any], kind: str, group_id: str) -> int:
    return max([
        int(entry.get("order", -1))
        for entry in data.get("publications" if kind == "publication" else "teaching", [])
        if entry.get("group_id") == group_id
    ] + [-1]) + 1


def add_publication(data: dict[str, Any], fields: dict[str, str]) -> str:
    entry_id = ORIGINAL_ADD_PUBLICATION(data, fields)
    _, entry = base.locate(data, entry_id)
    group = resolve_publication_group(data, fields, entry)
    entry["group_id"] = group["id"]
    entry["order"] = next_order(data, "publication", group["id"])
    normalize_orders(data, "publication")
    return entry_id


def teaching_duplicate(data: dict[str, Any], group_id: str, term: str, course: str) -> None:
    key = base.normalized_text(course)
    for item in data.get("teaching", []):
        if item.get("group_id") != group_id:
            continue
        old_term = str((item.get("term") or {}).get("en") or "")
        old_course = str((item.get("course") or {}).get("en") or "")
        if old_term == term and base.normalized_text(old_course) == key:
            raise ValueError(f"Possible duplicate teaching entry (Entry ID: {item.get('id')}).")


def add_teaching(data: dict[str, Any], fields: dict[str, str]) -> str:
    group = resolve_teaching_group(data, fields)
    assert group is not None
    term_en = base.get(fields, "Term (English) / 學期英文", True)
    course_en = base.get(fields, "Course (English) / 課程英文", True)
    teaching_duplicate(data, str(group["id"]), term_en, course_en)

    translated = base.fill_chinese(data, "teaching", fields, {
        "term": (term_en, base.get(fields, "Term (Chinese) / 學期中文")),
        "course": (course_en, base.get(fields, "Course (Chinese) / 課程中文")),
    })
    role = v3.resolve_role(data, fields) or {"en": "Teaching Assistant", "zh": "助教"}
    order = next_order(data, "teaching", str(group["id"]))
    entry = {
        "id": base.unique_id(data, "teaching", str(order), course_en),
        "type": "teaching",
        "group_id": group["id"],
        "order": order,
        "role": role,
        "institution": dict(group["label"]),
        "term": {"en": term_en, "zh": translated["term"]},
        "course": {"en": course_en, "zh": translated["course"]},
    }
    data["teaching"].append(entry)
    normalize_orders(data, "teaching")
    return entry["id"]


def upsert_link(entry: dict[str, Any], label: str, url: str) -> bool:
    if not url.strip():
        return False
    normalized = base.normalize_url(url)
    links = [link for link in entry.get("links", []) if str((link.get("label") or {}).get("en") or "") != label]
    zh_label = "期刊頁面" if label == "Journal" else "程式碼" if label == "Code" else label
    links.append({"label": {"en": label, "zh": zh_label}, "url": normalized})
    entry["links"] = links
    return True


def edit_entry(data: dict[str, Any], fields: dict[str, str]) -> str:
    entry_id = base.get(fields, "Entry ID / 項目 ID", True)
    _, before = base.locate(data, entry_id)
    old_group = str(before.get("group_id") or "")

    # Map the new dynamic institution selector to v3's existing edit fields.
    mapped = dict(fields)
    teaching_group = None
    if before.get("type") == "teaching":
        teaching_group = resolve_teaching_group(data, fields, edit=True)
        if teaching_group:
            mapped["New institution (English or shortcut) / 新機構英文或簡寫"] = group_label(teaching_group, "en")
            mapped["New institution (Chinese) / 新機構中文"] = group_label(teaching_group, "zh")

    entry_id = ORIGINAL_EDIT_ENTRY(data, mapped)
    _, entry = base.locate(data, entry_id)

    if entry.get("type") == "teaching":
        if teaching_group:
            entry["group_id"] = teaching_group["id"]
            entry["institution"] = dict(teaching_group["label"])
            if old_group != teaching_group["id"]:
                entry["order"] = next_order(data, "teaching", str(teaching_group["id"]))
        normalize_orders(data, "teaching")
        cleanup_empty_groups(data)
        return entry_id

    if entry.get("type") == "publication":
        metadata_changed = False
        venue_en = base.get(fields, "New venue or status (English) / 新期刊或狀態英文")
        venue_zh = base.get(fields, "New venue or status (Chinese) / 新期刊或狀態中文")
        if venue_en:
            if not venue_zh:
                venue_zh = base.fill_chinese(data, "publication", fields, {"venue": (venue_en, "")})["venue"]
            entry["venue"] = {"en": venue_en, "zh": venue_zh or venue_en}
            entry["venue_html"] = {
                "en": base.limited_markup(venue_en),
                "zh": base.limited_markup(venue_zh or venue_en),
            }
            metadata_changed = True

        arxiv = base.get(fields, "New arXiv number / 新 arXiv 編號")
        if arxiv:
            entry["arxiv"] = arxiv
            upsert_link(entry, "arXiv", f"https://arxiv.org/abs/{arxiv}")
        metadata_changed |= upsert_link(entry, "PDF", base.get(fields, "New PDF URL / 新 PDF 連結"))
        metadata_changed |= upsert_link(entry, "DOI", base.get(fields, "New DOI URL / 新 DOI 連結"))
        metadata_changed |= upsert_link(entry, "Journal", base.get(fields, "New journal page URL / 新期刊頁面連結"))
        metadata_changed |= upsert_link(entry, "Code", base.get(fields, "New code URL / 新程式碼連結"))
        # The old generic description field may also have updated venue metadata.
        metadata_changed |= bool(base.get(fields, "New English description/organization/term / 新英文說明、單位或學期"))

        group = resolve_publication_group(data, fields, entry, edit=True, metadata_changed=metadata_changed)
        entry["group_id"] = group["id"]
        if old_group != group["id"]:
            entry["order"] = next_order(data, "publication", str(group["id"]))
        normalize_orders(data, "publication")
        cleanup_empty_groups(data)

    return entry_id


def cleanup_empty_groups(data: dict[str, Any]) -> None:
    for kind, section in (("publication", "publications"), ("teaching", "teaching")):
        used = {str(entry.get("group_id") or "") for entry in data.get(section, [])}
        kept = []
        for group in content_groups(data, kind):
            if group.get("id") in used or (kind == "publication" and group.get("preset")):
                kept.append(group)
        data.setdefault("settings", {}).setdefault("content_groups", {})[kind] = kept
        normalize_orders(data, kind)


def remove_entry(data: dict[str, Any], fields: dict[str, str]) -> str:
    entry_id = base.get(fields, "Entry ID / 項目 ID", True)
    _, existing = base.locate(data, entry_id)
    kind = str(existing.get("type") or "")
    entry_id = ORIGINAL_REMOVE_ENTRY(data, fields)
    cleanup_empty_groups(data)
    if kind in UNGROUPED_KINDS:
        sync_ungrouped_order(data, kind)
    return entry_id


def reorder_entries(data: dict[str, Any], fields: dict[str, str]) -> str:
    raw = base.get(fields, "Ordering payload / 排序資料", True)
    payload = parse_ordering_payload(raw)

    kind = str(payload.get("kind") or "").strip().casefold()
    if kind not in SORTABLE_KINDS:
        supported = ", ".join(sorted(SORTABLE_KINDS))
        raise ValueError(f"Unsupported ordering kind: {kind}. Supported kinds: {supported}.")

    if kind in UNGROUPED_KINDS:
        entries = entries_of_kind(data, kind)
        ids_raw = payload.get("entries")
        if not isinstance(ids_raw, list):
            raise ValueError(f"{kind} ordering requires an entries array.")
        ids = [str(value) for value in ids_raw]
        current = {str(entry.get("id")) for entry in entries}
        if len(ids) != len(set(ids)):
            raise ValueError(f"{kind} ordering contains a duplicate Entry ID.")
        if set(ids) != current:
            missing = sorted(current - set(ids))
            unknown = sorted(set(ids) - current)
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if unknown:
                details.append("unknown: " + ", ".join(unknown))
            raise ValueError(
                f"{kind} ordering must contain every Entry ID exactly once"
                + (" (" + "; ".join(details) + ")" if details else "")
                + "."
            )
        entry_order_settings(data)[kind] = ids
        mark_manually_ordered(data, kind)
        return f"reorder-{kind}"

    section = "publications" if kind == "publication" else "teaching"
    groups_payload = payload.get("groups")
    if not isinstance(groups_payload, list):
        raise ValueError("Grouped ordering requires a groups array.")
    existing_groups = {str(group.get("id")): group for group in content_groups(data, kind)}
    seen_groups: list[str] = []
    seen_entries: list[str] = []
    by_id = {str(entry.get("id")): entry for entry in data.get(section, [])}

    for group_order, row in enumerate(groups_payload):
        gid = str((row or {}).get("id") or "")
        if gid not in existing_groups:
            raise ValueError(f"Unknown group ID in ordering: {gid}")
        if gid in seen_groups:
            raise ValueError(f"Duplicate group ID in ordering: {gid}")
        seen_groups.append(gid)
        existing_groups[gid]["order"] = group_order
        entries = [str(x) for x in (row or {}).get("entries", [])]
        for entry_order, entry_id in enumerate(entries):
            if entry_id not in by_id:
                raise ValueError(f"Unknown Entry ID in ordering: {entry_id}")
            if entry_id in seen_entries:
                raise ValueError(f"Duplicate Entry ID in ordering: {entry_id}")
            seen_entries.append(entry_id)
            by_id[entry_id]["group_id"] = gid
            by_id[entry_id]["order"] = entry_order

    current_ids = set(by_id)
    if set(seen_entries) != current_ids:
        missing = sorted(current_ids - set(seen_entries))
        raise ValueError(f"Ordering must include every {kind} Entry ID. Missing: {', '.join(missing)}")

    # Keep unused preset groups after used groups; custom empty groups are removed.
    next_group_order = len(seen_groups)
    for gid, group in existing_groups.items():
        if gid not in seen_groups:
            group["order"] = next_group_order
            next_group_order += 1
    cleanup_empty_groups(data)
    normalize_orders(data, kind)
    return f"reorder-{kind}"


def process(title: str, fields: dict[str, str], data: dict[str, Any]) -> tuple[str, str]:
    migrate_data(data)
    if title.startswith("[Website: Add publication]"):
        return "Added publication", add_publication(data, fields)
    if title.startswith("[Website: Add teaching]"):
        return "Added teaching course", add_teaching(data, fields)
    if title.startswith("[Website: Edit]"):
        return "Edited entry", edit_entry(data, fields)
    if title.startswith("[Website: Remove]"):
        return "Removed entry", remove_entry(data, fields)
    if title.startswith("[Website: Reorder]"):
        return "Reordered website entries", reorder_entries(data, fields)
    action, entry_id = ORIGINAL_PROCESS(title, fields, data)
    try:
        _, entry = base.locate(data, entry_id)
        kind = str(entry.get("type") or "")
    except ValueError:
        kind = ""
    if kind in UNGROUPED_KINDS:
        sync_ungrouped_order(data, kind)
    return action, entry_id


base.load_data = load_data
base.add_publication = add_publication
base.add_teaching = add_teaching
base.edit_entry = edit_entry
base.remove_entry = remove_entry
base.process = process


if __name__ == "__main__":
    base.main()
