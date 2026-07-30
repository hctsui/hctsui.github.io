#!/usr/bin/env python3
"""Process website Issue Forms using only an explicit bilingual dictionary.

There is deliberately no AI, fuzzy matching, series-title inference, static
translation list, or translation memory harvested from site.json.  Blank
counterparts are filled only by exact pairs stored in content/translations.json.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
TRANSLATIONS_FILE = ROOT / "content" / "translations.json"
WARNINGS: list[str] = []
NOTES: list[str] = []

PRESET_PUBLICATION_GROUPS = [
    {"id": "journal-articles", "label": {"en": "Journal Articles", "zh": "期刊論文"}, "order": 0, "preset": True},
    {"id": "preprints", "label": {"en": "Preprints", "zh": "預印本"}, "order": 1, "preset": True},
    {"id": "survey-papers", "label": {"en": "Survey Papers", "zh": "綜述論文"}, "order": 2, "preset": True},
]
DEFAULT_INSTITUTION = {"en": "National Tsing Hua University", "zh": "國立清華大學"}
ROLE_FIXED = {
    "teaching assistant": {"en": "Teaching Assistant", "zh": "助教"},
    "lecturer": {"en": "Lecturer", "zh": "講師"},
}
GROUPED_KINDS = {"publication", "teaching"}
UNGROUPED_KINDS = {"conference", "talk", "visit", "honor"}
SORTABLE_KINDS = GROUPED_KINDS | UNGROUPED_KINDS


def load_data() -> dict[str, Any]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return migrate_data(data)


def save_data(data: dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(label: str) -> str:
    label = re.sub(
        r"\s*[\[（(](?:必填|條件必填|選填|required|optional|選填・可由對照表補全)[\]）)]",
        "",
        label,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", label).strip()


def parse_form(body: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for raw in body.splitlines():
        if raw.startswith("### "):
            current = normalize_label(raw[4:].strip())
            fields[current] = []
        elif current is not None:
            fields[current].append(raw)
    result: dict[str, str] = {}
    for key, lines in fields.items():
        value = "\n".join(lines).strip()
        if value in {"_No response_", "No response", "None", "無"}:
            value = ""
        result[key] = value
    return result


def get(fields: dict[str, str], label: str, required: bool = False) -> str:
    value = fields.get(label, "").strip()
    if required and not value:
        raise ValueError(f"Missing required field: {label}")
    return value


def iso(value: str, label: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD: {value}") from exc


def yes(value: str) -> bool:
    return value.strip().casefold().startswith(("yes", "是"))


def dictionary_enabled(fields: dict[str, str]) -> bool:
    mode = get(fields, "Bilingual completion / 雙語欄位補全")
    folded = mode.casefold()
    return folded.startswith("use admin dictionary") or "使用 admin 中英對照表" in folded


def normalize_lookup(value: str) -> str:
    text = unicodedata.normalize("NFKC", strip_markup(value))
    return re.sub(r"\s+", " ", text).strip().casefold()


class TranslationIndex:
    def __init__(self) -> None:
        raw = {"pairs": []}
        if TRANSLATIONS_FILE.exists():
            raw = json.loads(TRANSLATIONS_FILE.read_text(encoding="utf-8"))
        pairs = raw.get("pairs", [])
        if not isinstance(pairs, list):
            raise ValueError("content/translations.json: pairs must be an array.")
        self.en_to_zh: dict[str, str] = {}
        self.zh_to_en: dict[str, str] = {}
        for row in pairs:
            if not isinstance(row, dict):
                continue
            en = str(row.get("en") or "").strip()
            zh = str(row.get("zh") or "").strip()
            if not en or not zh:
                continue
            en_key, zh_key = normalize_lookup(en), normalize_lookup(zh)
            if en_key in self.en_to_zh and self.en_to_zh[en_key] != zh:
                raise ValueError(f"Conflicting Chinese translations for: {en}")
            if zh_key in self.zh_to_en and self.zh_to_en[zh_key] != en:
                raise ValueError(f"Conflicting English translations for: {zh}")
            self.en_to_zh[en_key] = zh
            self.zh_to_en[zh_key] = en

    def complete(self, en: str, zh: str) -> tuple[str, str]:
        """Complete only by exact whole-field dictionary lookup."""
        en, zh = en.strip(), zh.strip()
        if en and not zh:
            zh = self.en_to_zh.get(normalize_lookup(en), "")
        elif zh and not en:
            en = self.zh_to_en.get(normalize_lookup(zh), "")
        return en, zh


_TERM_EN_TO_ZH = {
    "spring": "春",
    "summer": "夏",
    "fall": "秋",
    "autumn": "秋",
    "winter": "冬",
}
_TERM_ZH_TO_EN = {
    "春": "Spring",
    "春季": "Spring",
    "夏": "Summer",
    "夏季": "Summer",
    "秋": "Fall",
    "秋季": "Fall",
    "冬": "Winter",
    "冬季": "Winter",
}


def complete_academic_term(en: str, zh: str) -> tuple[str, str]:
    """Complete recurring semester labels without enumerating every year.

    Supported examples:
      Fall 2026 / 2026 Fall / Autumn 2026 -> 2026 秋
      2026 秋 / 2026 秋季 -> Fall 2026

    This rule runs only when Admin dictionary completion is enabled.
    It does not perform keyword replacement inside longer text.
    """
    en, zh = en.strip(), zh.strip()

    if en and not zh:
        normalized = re.sub(r"\s+", " ", en).strip()
        match = re.fullmatch(
            r"(?i)(spring|summer|fall|autumn|winter)\s+([12]\d{3})",
            normalized,
        )
        if not match:
            match = re.fullmatch(
                r"(?i)([12]\d{3})\s+(spring|summer|fall|autumn|winter)",
                normalized,
            )
            if match:
                year, season = match.group(1), match.group(2).casefold()
            else:
                year = season = ""
        else:
            season, year = match.group(1).casefold(), match.group(2)
        if year and season:
            return en, f"{year} {_TERM_EN_TO_ZH[season]}"

    if zh and not en:
        normalized = re.sub(r"\s+", " ", zh).strip()
        match = re.fullmatch(r"([12]\d{3})\s*年?\s*(春季?|夏季?|秋季?|冬季?)", normalized)
        if match:
            year, season = match.group(1), match.group(2)
            return f"{_TERM_ZH_TO_EN[season]} {year}", zh

    return en, zh


_TRANSLATIONS: TranslationIndex | None = None


def translations() -> TranslationIndex:
    global _TRANSLATIONS
    if _TRANSLATIONS is None:
        _TRANSLATIONS = TranslationIndex()
    return _TRANSLATIONS


def bilingual_pair(
    fields: dict[str, str],
    en_label: str,
    zh_label: str,
    *,
    require_any: bool = False,
    name: str = "bilingual field",
) -> tuple[str, str]:
    en, zh = get(fields, en_label), get(fields, zh_label)
    if dictionary_enabled(fields):
        before = (en, zh)
        # Academic terms use a small deterministic year+season rule first.
        # Every other bilingual field uses exact whole-field dictionary lookup only.
        if name == "學期":
            en, zh = complete_academic_term(en, zh)
        en, zh = translations().complete(en, zh)
        if before != (en, zh):
            source_name = "學期格式規則或 Admin 中英對照表" if name == "學期" else "Admin 中英對照表"
            NOTES.append(f"由{source_name}補全{name}。")
    if require_any and not (en or zh):
        raise ValueError(f"At least one language is required for {name}.")
    return en, zh


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if any(ch.isspace() for ch in value):
        raise ValueError(f"URL cannot contain spaces: {value}")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.I):
        value = "https://" + value.lstrip("/")
    return value


def strip_markup(value: str) -> str:
    return re.sub(r"\[/?(?:i|b)\]", "", value, flags=re.I).strip()


def limited_markup(value: str) -> str:
    out = html.escape(value.strip(), quote=False)
    out = re.sub(r"\[i\](.+?)\[/i\]", r"<em>\1</em>", out, flags=re.I | re.S)
    out = re.sub(r"\[b\](.+?)\[/b\]", r"<strong>\1</strong>", out, flags=re.I | re.S)
    return out


def mark_self(value: str, lang: str) -> str:
    escaped = limited_markup(value)
    name = "崔鴻竣" if lang == "zh" else "Hung-Chun Tsui"
    escaped_name = html.escape(name)
    if escaped_name and f"<strong>{escaped_name}</strong>" not in escaped:
        escaped = escaped.replace(escaped_name, f"<strong>{escaped_name}</strong>")
    return escaped


def match_key(value: str) -> str:
    text = unicodedata.normalize("NFKC", strip_markup(value)).casefold()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def unique_id(data: dict[str, Any], kind: str, anchor: str, title: str) -> str:
    existing = {
        item.get("id")
        for section in ("activities", "honors", "publications", "teaching")
        for item in data.get(section, [])
    }
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", strip_markup(title).casefold()).strip("-")[:46]
    if not ascii_slug:
        ascii_slug = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
    candidate = f"{kind}-{anchor}-{ascii_slug}".strip("-")
    if candidate not in existing:
        return candidate
    digest = hashlib.sha1(f"{kind}|{anchor}|{title}|{len(existing)}".encode()).hexdigest()[:7]
    return f"{candidate}-{digest}"


def ensure_not_duplicate(data: dict[str, Any], kind: str, anchor: str, en: str, zh: str) -> None:
    keys = {match_key(value) for value in (en, zh) if value.strip()}
    for item in data.get("activities", []) + data.get("honors", []) + data.get("publications", []) + data.get("teaching", []):
        if item.get("type") != kind:
            continue
        old_anchor = str(item.get("start_date") or item.get("date") or item.get("year") or "")
        pair = item.get("title") or item.get("course") or {}
        old_keys = {match_key(str(pair.get(lang) or "")) for lang in ("en", "zh") if str(pair.get(lang) or "").strip()}
        if old_anchor == anchor and keys & old_keys:
            raise ValueError(f"Possible duplicate (Entry ID: {item.get('id')}).")


def location(*parts: str) -> str:
    return ", ".join(part.strip() for part in parts if part.strip())


def selected_group_id(value: str) -> str:
    match = re.search(r"\[([a-z0-9][a-z0-9-]*)\]\s*$", value.strip(), flags=re.I)
    return match.group(1).casefold() if match else ""


def slugify(value: str) -> str:
    original = unicodedata.normalize("NFKC", strip_markup(value)).strip()
    ascii_value = original.casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:70] if slug else "group-" + hashlib.sha1(original.encode("utf-8")).hexdigest()[:12]


def content_groups(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return data.setdefault("settings", {}).setdefault("content_groups", {}).setdefault(kind, [])


def group_label(group: dict[str, Any], lang: str = "en") -> str:
    label = group.get("label") or {}
    return str(label.get(lang) or "") if isinstance(label, dict) else str(label or "")


def ensure_group(data: dict[str, Any], kind: str, label: dict[str, str], *, group_id: str | None = None, preset: bool = False) -> dict[str, Any]:
    wanted_id = group_id or slugify(label.get("en") or label.get("zh") or "group")
    groups = content_groups(data, kind)
    for group in groups:
        if group.get("id") == wanted_id:
            group.setdefault("label", {})
            for lang in ("en", "zh"):
                if label.get(lang):
                    group["label"][lang] = label[lang]
                else:
                    group["label"].setdefault(lang, "")
            if preset:
                group["preset"] = True
            return group
    order = max([int(g.get("order", -1)) for g in groups] + [-1]) + 1
    group = {"id": wanted_id, "label": {"en": label.get("en", ""), "zh": label.get("zh", "")}, "order": order}
    if preset:
        group["preset"] = True
    groups.append(group)
    return group


def find_group(data: dict[str, Any], kind: str, group_id: str) -> dict[str, Any] | None:
    return next((g for g in content_groups(data, kind) if g.get("id") == group_id), None)


def normalize_orders(data: dict[str, Any], kind: str) -> None:
    groups = sorted(content_groups(data, kind), key=lambda g: (int(g.get("order", 999999)), str(g.get("id", ""))))
    section = "publications" if kind == "publication" else "teaching"
    for group_order, group in enumerate(groups):
        group["order"] = group_order
        entries = [e for e in data.get(section, []) if e.get("group_id") == group.get("id")]
        entries.sort(key=lambda e: (int(e.get("order", 999999)), str(e.get("id", ""))))
        for entry_order, entry in enumerate(entries):
            entry["order"] = entry_order


def entries_of_kind(data: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    if kind in {"conference", "talk", "visit"}:
        return [x for x in data.get("activities", []) if x.get("type") == kind]
    return list(data.get({"honor": "honors", "publication": "publications", "teaching": "teaching"}[kind], []))


def entry_order_settings(data: dict[str, Any]) -> dict[str, list[str]]:
    value = data.setdefault("settings", {}).setdefault("entry_order", {})
    return value if isinstance(value, dict) else {}


def manually_ordered_kinds(data: dict[str, Any]) -> set[str]:
    raw = data.setdefault("settings", {}).setdefault("manually_ordered_kinds", [])
    return {str(x) for x in raw} if isinstance(raw, list) else set()


def mark_manually_ordered(data: dict[str, Any], kind: str) -> None:
    kinds = manually_ordered_kinds(data)
    kinds.add(kind)
    data.setdefault("settings", {})["manually_ordered_kinds"] = sorted(kinds)


def default_ungrouped_ids(data: dict[str, Any], kind: str) -> list[str]:
    entries = entries_of_kind(data, kind)
    if kind == "honor":
        entries.sort(key=lambda x: (-int(x.get("year", 0)), int(x.get("order", 999999)), str(x.get("id", ""))))
    else:
        entries.sort(key=lambda x: (str(x.get("start_date", "")), str(x.get("id", ""))), reverse=True)
    return [str(x.get("id")) for x in entries]


def sync_ungrouped_order(data: dict[str, Any], kind: str) -> None:
    current = {str(x.get("id")) for x in entries_of_kind(data, kind)}
    defaults = [x for x in default_ungrouped_ids(data, kind) if x in current]
    orders = data.setdefault("settings", {}).setdefault("entry_order", {})
    if kind not in manually_ordered_kinds(data):
        orders[kind] = defaults
    else:
        previous = [str(x) for x in orders.get(kind, []) if str(x) in current]
        orders[kind] = previous + [x for x in defaults if x not in previous]


def publication_has_link(entry: dict[str, Any], label: str) -> bool:
    return any(str((x.get("label") or {}).get("en") or "").casefold() == label.casefold() and x.get("url") for x in entry.get("links", []))


def publication_group_id(entry: dict[str, Any]) -> str:
    if publication_has_link(entry, "DOI") or publication_has_link(entry, "Journal"):
        return "journal-articles"
    venue = str((entry.get("venue") or {}).get("en") or "").strip().casefold()
    if not venue or venue.startswith("arxiv:") or any(x in venue for x in ("submitted", "under review", "preprint", "in preparation", "manuscript")):
        return "preprints"
    if any(x in venue for x in ("accepted", "to appear", "published", "forthcoming", "vol.", "volume ", "issue ", "no.", "journal", "proceedings", "transactions")):
        return "journal-articles"
    if re.search(r"\b\d{1,4}\b.*(?:\(|\)|:|--|–)", venue):
        return "journal-articles"
    return "preprints"


def migrate_data(data: dict[str, Any]) -> dict[str, Any]:
    for preset in PRESET_PUBLICATION_GROUPS:
        ensure_group(data, "publication", dict(preset["label"]), group_id=preset["id"], preset=True)
    nthu = ensure_group(data, "teaching", DEFAULT_INSTITUTION, group_id="national-tsing-hua-university")
    for entry in data.get("publications", []):
        if not find_group(data, "publication", str(entry.get("group_id") or "")):
            entry["group_id"] = publication_group_id(entry)
    for entry in data.get("teaching", []):
        institution = entry.get("institution") if isinstance(entry.get("institution"), dict) else {}
        if not (institution.get("en") or institution.get("zh")):
            institution = dict(DEFAULT_INSTITUTION)
        if str(institution.get("en") or "").casefold() == "nthu":
            institution = dict(DEFAULT_INSTITUTION)
        gid = str(entry.get("group_id") or slugify(str(institution.get("en") or institution.get("zh") or "institution")))
        group = ensure_group(data, "teaching", {"en": str(institution.get("en") or ""), "zh": str(institution.get("zh") or "")}, group_id=gid)
        entry["group_id"] = group["id"]
        entry["institution"] = dict(group["label"])
        entry.setdefault("role", {"en": "Teaching Assistant", "zh": "助教"})
    normalize_orders(data, "publication")
    normalize_orders(data, "teaching")
    for kind in sorted(UNGROUPED_KINDS):
        sync_ungrouped_order(data, kind)
    return data


def next_order(data: dict[str, Any], kind: str, group_id: str) -> int:
    section = "publications" if kind == "publication" else "teaching"
    return max([int(x.get("order", -1)) for x in data.get(section, []) if x.get("group_id") == group_id] + [-1]) + 1


def resolve_custom_group(data: dict[str, Any], kind: str, fields: dict[str, str], en_label: str, zh_label: str) -> dict[str, Any]:
    en, zh = bilingual_pair(fields, en_label, zh_label, require_any=True, name="自訂大標題")
    return ensure_group(data, kind, {"en": en, "zh": zh})


def resolve_publication_group(data: dict[str, Any], fields: dict[str, str], entry: dict[str, Any], *, edit: bool = False, metadata_changed: bool = False) -> dict[str, Any]:
    label = "New publication section / 新論文大標題" if edit else "Publication section / 論文大標題"
    selected = get(fields, label).strip()
    lowered = selected.casefold()
    if edit and (not selected or lowered.startswith("keep unchanged") or lowered.startswith("維持不變")):
        if metadata_changed and publication_group_id(entry) == "journal-articles":
            return find_group(data, "publication", "journal-articles") or ensure_group(data, "publication", PRESET_PUBLICATION_GROUPS[0]["label"], group_id="journal-articles", preset=True)
        current = find_group(data, "publication", str(entry.get("group_id") or ""))
        if current:
            return current
    if not selected or lowered.startswith("auto") or "自動判斷" in selected:
        gid = publication_group_id(entry)
        return find_group(data, "publication", gid) or ensure_group(data, "publication", {"en": gid.replace("-", " ").title(), "zh": ""}, group_id=gid)
    if lowered.startswith("other") or "其他" in selected:
        return resolve_custom_group(
            data, "publication", fields,
            "New custom publication section (English) / 新自訂論文大標題英文" if edit else "Custom publication section (English) / 自訂論文大標題英文",
            "New custom publication section (Chinese) / 新自訂論文大標題中文" if edit else "Custom publication section (Chinese) / 自訂論文大標題中文",
        )
    group = find_group(data, "publication", selected_group_id(selected))
    if not group:
        raise ValueError(f"Unknown publication section option: {selected}")
    return group


def resolve_teaching_group(data: dict[str, Any], fields: dict[str, str], *, edit: bool = False) -> dict[str, Any] | None:
    label = "New institution section / 新機構大標題" if edit else "Institution section / 機構大標題"
    selected = get(fields, label).strip()
    lowered = selected.casefold()
    if edit and (not selected or lowered.startswith("keep unchanged") or lowered.startswith("維持不變")):
        return None
    if lowered.startswith("other") or "其他" in selected:
        return resolve_custom_group(
            data, "teaching", fields,
            "New custom institution (English) / 新自訂機構英文" if edit else "Custom institution (English) / 自訂機構英文",
            "New custom institution (Chinese) / 新自訂機構中文" if edit else "Custom institution (Chinese) / 自訂機構中文",
        )
    group = find_group(data, "teaching", selected_group_id(selected))
    if not group:
        raise ValueError(f"Unknown institution option: {selected}")
    return group


def resolve_role(fields: dict[str, str], *, edit: bool = False) -> dict[str, str] | None:
    label = "New teaching role / 新教學身分" if edit else "Role / 教學身分"
    selected = get(fields, label).strip()
    lowered = selected.casefold()
    if edit and (not selected or lowered.startswith("keep unchanged") or lowered.startswith("維持不變")):
        return None
    for prefix, pair in ROLE_FIXED.items():
        if lowered.startswith(prefix):
            return dict(pair)
    if lowered.startswith("other") or "其他" in selected:
        en, zh = bilingual_pair(
            fields,
            "New custom role (English) / 新自訂身分英文" if edit else "Custom role (English) / 自訂身分英文",
            "New custom role (Chinese) / 新自訂身分中文" if edit else "Custom role (Chinese) / 自訂身分中文",
            require_any=True,
            name="自訂教學身分",
        )
        return {"en": en, "zh": zh}
    raise ValueError(f"Unknown teaching role option: {selected}")


def add_conference(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Start date / 開始日期", True), "Start date")
    end = iso(get(f, "End date / 結束日期") or start, "End date")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")
    title_en, title_zh = bilingual_pair(f, "Conference name (English) / 會議英文名稱", "Conference name (Chinese) / 會議中文名稱", require_any=True, name="會議名稱")
    venue_en, venue_zh = bilingual_pair(f, "Venue (English) / 地點英文", "Venue (Chinese) / 地點中文", name="地點")
    city_en, city_zh = bilingual_pair(f, "City (English) / 城市英文", "City (Chinese) / 城市中文", name="城市")
    country_en, country_zh = bilingual_pair(f, "Country (English) / 國家英文", "Country (Chinese) / 國家中文", name="國家")
    ensure_not_duplicate(data, "conference", start, title_en, title_zh)
    anchor = title_en or title_zh
    entry = {
        "id": unique_id(data, "conference", start, anchor), "type": "conference", "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "url": normalize_url(get(f, "Conference URL / 會議連結")),
        "description": {"en": location(venue_en, city_en, country_en), "zh": location(venue_zh, city_zh, country_zh)},
        "slides_url": "",
    }
    entry["description_html"] = {lang: limited_markup(value) for lang, value in entry["description"].items()}
    data["activities"].append(entry)
    sync_ungrouped_order(data, "conference")
    return entry["id"]


def add_talk(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Talk date / 演講日期", True), "Talk date")
    end = iso(get(f, "End date (optional) / 結束日期（選填）") or get(f, "End date (optional) / 結束日期") or start, "End date")
    title_en, title_zh = bilingual_pair(f, "Talk title (English) / 演講英文題目", "Talk title (Chinese) / 演講中文題目", require_any=True, name="演講題目")
    event_en, event_zh = bilingual_pair(f, "Event (English) / 活動英文名稱", "Event (Chinese) / 活動中文名稱", name="活動名稱")
    inst_en, inst_zh = bilingual_pair(f, "Institution (English) / 機構英文", "Institution (Chinese) / 機構中文", name="機構")
    city_en, city_zh = bilingual_pair(f, "City (English) / 城市英文", "City (Chinese) / 城市中文", name="城市")
    country_en, country_zh = bilingual_pair(f, "Country (English) / 國家英文", "Country (Chinese) / 國家中文", name="國家")
    ensure_not_duplicate(data, "talk", start, title_en, title_zh)
    anchor = title_en or title_zh
    entry = {
        "id": unique_id(data, "talk", start, anchor), "type": "talk", "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "url": normalize_url(get(f, "Talk or event URL / 演講或活動連結")),
        "description": {"en": location(event_en, inst_en, city_en, country_en), "zh": location(event_zh, inst_zh, city_zh, country_zh)},
        "slides_url": normalize_url(get(f, "Slides URL / 投影片連結")),
    }
    entry["description_html"] = {lang: limited_markup(value) for lang, value in entry["description"].items()}
    data["activities"].append(entry)
    sync_ungrouped_order(data, "talk")
    return entry["id"]


def add_visit(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Start date / 開始日期", True), "Start date")
    end = iso(get(f, "End date / 結束日期") or start, "End date")
    inst_en, inst_zh = bilingual_pair(f, "Institution (English) / 機構英文", "Institution (Chinese) / 機構中文", require_any=True, name="訪問機構")
    city_en, city_zh = bilingual_pair(f, "City (English) / 城市英文", "City (Chinese) / 城市中文", name="城市")
    country_en, country_zh = bilingual_pair(f, "Country (English) / 國家英文", "Country (Chinese) / 國家中文", name="國家")
    funding_en, funding_zh = bilingual_pair(f, "Funding note (English) / 補助說明英文", "Funding note (Chinese) / 補助說明中文", name="補助說明")
    ensure_not_duplicate(data, "visit", start, inst_en, inst_zh)
    base_en, base_zh = location(city_en, country_en), location(city_zh, country_zh)
    desc_en = f"{base_en} · {funding_en}" if base_en and funding_en else base_en or funding_en
    desc_zh = f"{base_zh} · {funding_zh}" if base_zh and funding_zh else base_zh or funding_zh
    anchor = inst_en or inst_zh
    entry = {
        "id": unique_id(data, "visit", start, anchor), "type": "visit", "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(inst_en), "zh": strip_markup(inst_zh)},
        "title_html": {"en": limited_markup(inst_en), "zh": limited_markup(inst_zh)},
        "url": normalize_url(get(f, "Institution or visit URL / 機構或訪問連結")),
        "description": {"en": desc_en, "zh": desc_zh},
        "description_html": {"en": limited_markup(desc_en), "zh": limited_markup(desc_zh)},
        "slides_url": "",
    }
    data["activities"].append(entry)
    sync_ungrouped_order(data, "visit")
    return entry["id"]


def add_honor(data: dict[str, Any], f: dict[str, str]) -> str:
    year_text = get(f, "Year / 年份", True)
    if not re.fullmatch(r"\d{4}", year_text):
        raise ValueError("Year must contain four digits.")
    title_en, title_zh = bilingual_pair(f, "Honor name (English) / 獎項英文名稱", "Honor name (Chinese) / 獎項中文名稱", require_any=True, name="獎項名稱")
    org_en, org_zh = bilingual_pair(f, "Organization (English) / 頒發單位英文", "Organization (Chinese) / 頒發單位中文", name="頒發單位")
    ensure_not_duplicate(data, "honor", year_text, title_en, title_zh)
    anchor = title_en or title_zh
    entry = {
        "id": unique_id(data, "honor", year_text, anchor), "type": "honor", "year": int(year_text), "order": 0,
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "url": normalize_url(get(f, "Honor URL / 獎項連結")),
        "organization": {"en": org_en, "zh": org_zh},
        "organization_html": {"en": limited_markup(org_en), "zh": limited_markup(org_zh)},
    }
    data["honors"].append(entry)
    sync_ungrouped_order(data, "honor")
    return entry["id"]


def link_entry(label: str, url: str) -> dict[str, Any] | None:
    normalized = normalize_url(url)
    if not normalized:
        return None
    labels = {"Journal": "期刊頁面", "Code": "程式碼"}
    return {"label": {"en": label, "zh": labels.get(label, label)}, "url": normalized}


def add_publication(data: dict[str, Any], f: dict[str, str]) -> str:
    pub_date = iso(get(f, "Public date / 公開日期", True), "Public date")
    title_en, title_zh = bilingual_pair(f, "Title (English) / 英文題目", "Title (Chinese) / 中文題目", require_any=True, name="論文題目")
    authors_en, authors_zh = bilingual_pair(f, "Authors (English) / 作者英文", "Authors (Chinese) / 作者中文", require_any=True, name="作者")
    venue_en, venue_zh = bilingual_pair(f, "Venue or status (English) / 期刊或狀態英文", "Venue or status (Chinese) / 期刊或狀態中文", name="期刊或狀態")
    ensure_not_duplicate(data, "publication", pub_date, title_en, title_zh)
    arxiv = get(f, "arXiv number / arXiv 編號")
    candidates = [
        ("arXiv", get(f, "arXiv URL / arXiv 連結") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")),
        ("PDF", get(f, "PDF URL / PDF 連結")),
        ("DOI", get(f, "DOI URL / DOI 連結")),
        ("Journal", get(f, "Journal page URL / 期刊頁面連結")),
        ("Code", get(f, "Code URL / 程式碼連結")),
    ]
    links = [x for label, url in candidates if (x := link_entry(label, url))]
    provisional = {
        "id": "", "type": "publication", "date": pub_date, "year": int(pub_date[:4]), "arxiv": arxiv,
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "authors": {"en": strip_markup(authors_en), "zh": strip_markup(authors_zh)},
        "authors_html": {"en": mark_self(authors_en, "en"), "zh": mark_self(authors_zh, "zh")},
        "venue": {"en": venue_en, "zh": venue_zh},
        "venue_html": {"en": limited_markup(venue_en), "zh": limited_markup(venue_zh)},
        "links": links,
    }
    group = resolve_publication_group(data, f, provisional)
    anchor = title_en or title_zh
    provisional["id"] = unique_id(data, "publication", arxiv or pub_date, anchor)
    provisional["group_id"] = group["id"]
    provisional["order"] = next_order(data, "publication", group["id"])
    data["publications"].append(provisional)
    normalize_orders(data, "publication")
    return provisional["id"]


def teaching_duplicate(data: dict[str, Any], group_id: str, term_en: str, term_zh: str, course_en: str, course_zh: str) -> None:
    keys = {match_key(x) for x in (course_en, course_zh) if x}
    for item in data.get("teaching", []):
        if item.get("group_id") != group_id:
            continue
        old_term = item.get("term") or {}
        old_course = item.get("course") or {}
        term_matches = any(str(old_term.get(lang) or "") == value for lang in ("en", "zh") for value in (term_en, term_zh) if value)
        old_keys = {match_key(str(old_course.get(lang) or "")) for lang in ("en", "zh") if str(old_course.get(lang) or "")}
        if term_matches and keys & old_keys:
            raise ValueError(f"Possible duplicate teaching entry (Entry ID: {item.get('id')}).")


def add_teaching(data: dict[str, Any], f: dict[str, str]) -> str:
    group = resolve_teaching_group(data, f)
    assert group is not None
    term_en, term_zh = bilingual_pair(f, "Term (English) / 學期英文", "Term (Chinese) / 學期中文", require_any=True, name="學期")
    course_en, course_zh = bilingual_pair(f, "Course (English) / 課程英文", "Course (Chinese) / 課程中文", require_any=True, name="課程")
    teaching_duplicate(data, str(group["id"]), term_en, term_zh, course_en, course_zh)
    role = resolve_role(f) or {"en": "Teaching Assistant", "zh": "助教"}
    order = next_order(data, "teaching", str(group["id"]))
    anchor = course_en or course_zh
    entry = {
        "id": unique_id(data, "teaching", str(order), anchor), "type": "teaching", "group_id": group["id"], "order": order,
        "role": role, "institution": dict(group["label"]),
        "term": {"en": term_en, "zh": term_zh}, "course": {"en": course_en, "zh": course_zh},
    }
    data["teaching"].append(entry)
    normalize_orders(data, "teaching")
    return entry["id"]


def locate(data: dict[str, Any], entry_id: str) -> tuple[str, dict[str, Any]]:
    for section in ("activities", "honors", "publications", "teaching"):
        for item in data.get(section, []):
            if item.get("id") == entry_id:
                return section, item
    raise ValueError(f"Cannot find entry ID: {entry_id}")


CLEAR_VALUES = {"[clear]", "[清除]", "__clear__"}


def update_pair_from_edit(item: dict[str, Any], field: str, html_field: str | None, fields: dict[str, str], en_label: str, zh_label: str, *, authors: bool = False) -> bool:
    raw_en, raw_zh = get(fields, en_label), get(fields, zh_label)
    if not (raw_en or raw_zh):
        return False

    en_clear = raw_en.strip().casefold() in CLEAR_VALUES
    zh_clear = raw_zh.strip().casefold() in CLEAR_VALUES
    en = "" if en_clear else raw_en
    zh = "" if zh_clear else raw_zh

    if dictionary_enabled(fields):
        # An explicit clear always wins; the dictionary must not refill that side.
        if en and not zh and not zh_clear:
            _, zh = translations().complete(en, "")
        elif zh and not en and not en_clear:
            en, _ = translations().complete("", zh)

    pair = item.setdefault(field, {})
    rich = item.setdefault(html_field, {}) if html_field else None

    if en_clear:
        pair["en"] = ""
        if rich is not None:
            rich["en"] = ""
    elif en:
        pair["en"] = strip_markup(en) if field in {"title", "authors"} else en
        if rich is not None:
            rich["en"] = mark_self(en, "en") if authors else limited_markup(en)

    if zh_clear:
        pair["zh"] = ""
        if rich is not None:
            rich["zh"] = ""
    elif zh:
        pair["zh"] = strip_markup(zh) if field in {"title", "authors"} else zh
        if rich is not None:
            rich["zh"] = mark_self(zh, "zh") if authors else limited_markup(zh)
    return True


def upsert_link(entry: dict[str, Any], label: str, url: str) -> bool:
    if not url.strip():
        return False
    link = link_entry(label, url)
    links = [x for x in entry.get("links", []) if str((x.get("label") or {}).get("en") or "") != label]
    if link:
        links.append(link)
    entry["links"] = links
    return True


def edit_entry(data: dict[str, Any], f: dict[str, str]) -> str:
    entry_id = get(f, "Entry ID / 項目 ID", True)
    _, item = locate(data, entry_id)
    kind = str(item.get("type"))
    old_group = str(item.get("group_id") or "")

    if kind == "teaching":
        update_pair_from_edit(item, "course", None, f, "New English title/name/course / 新英文題目、名稱或課名", "New Chinese title/name/course / 新中文題目、名稱或課名")
    else:
        update_pair_from_edit(item, "title", "title_html", f, "New English title/name/course / 新英文題目、名稱或課名", "New Chinese title/name/course / 新中文題目、名稱或課名")

    start, end, year = get(f, "New start/public date / 新開始或公開日期"), get(f, "New end date / 新結束日期"), get(f, "New year / 新年份")
    if start:
        start = iso(start, "New date")
        if kind == "publication":
            item["date"], item["year"] = start, int(start[:4])
        else:
            item["start_date"] = start
    if end and kind in {"conference", "talk", "visit"}:
        item["end_date"] = iso(end, "New end date")
    if year and kind == "honor":
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError("New year must contain four digits.")
        item["year"] = int(year)
    if get(f, "New main URL / 新主要連結"):
        item["url"] = normalize_url(get(f, "New main URL / 新主要連結"))

    desc_en_label = "New English description/organization/term / 新英文說明、單位或學期"
    desc_zh_label = "New Chinese description/organization/term / 新中文說明、單位或學期"
    if kind in {"conference", "talk", "visit"}:
        update_pair_from_edit(item, "description", "description_html", f, desc_en_label, desc_zh_label)
    elif kind == "honor":
        update_pair_from_edit(item, "organization", "organization_html", f, desc_en_label, desc_zh_label)
    elif kind == "teaching":
        update_pair_from_edit(item, "term", None, f, desc_en_label, desc_zh_label)
    elif kind == "publication":
        update_pair_from_edit(item, "venue", "venue_html", f, desc_en_label, desc_zh_label)
        update_pair_from_edit(item, "authors", "authors_html", f, "New authors (English) / 新作者英文", "New authors (Chinese) / 新作者中文", authors=True)

    auxiliary = get(f, "New slides or PDF URL / 新投影片或 PDF 連結")
    if auxiliary:
        if kind == "talk":
            item["slides_url"] = normalize_url(auxiliary)
        elif kind == "publication":
            upsert_link(item, "PDF", auxiliary)

    if kind in {"conference", "talk", "visit"}:
        upcoming = get(f, "Upcoming setting / Upcoming 設定")
        if upcoming.startswith(("Yes", "是")):
            item["show_upcoming"] = True
        elif upcoming.startswith(("No", "否")):
            item["show_upcoming"] = False
        sync_ungrouped_order(data, kind)

    if kind == "teaching":
        group = resolve_teaching_group(data, f, edit=True)
        if group:
            item["group_id"], item["institution"] = group["id"], dict(group["label"])
            if old_group != group["id"]:
                item["order"] = next_order(data, "teaching", group["id"])
        role = resolve_role(f, edit=True)
        if role:
            item["role"] = role
        normalize_orders(data, "teaching")
        cleanup_empty_groups(data)

    if kind == "publication":
        metadata_changed = False
        if get(f, "New venue or status (English) / 新期刊或狀態英文") or get(f, "New venue or status (Chinese) / 新期刊或狀態中文"):
            metadata_changed = update_pair_from_edit(item, "venue", "venue_html", f, "New venue or status (English) / 新期刊或狀態英文", "New venue or status (Chinese) / 新期刊或狀態中文")
        arxiv = get(f, "New arXiv number / 新 arXiv 編號")
        if arxiv:
            item["arxiv"] = arxiv
            upsert_link(item, "arXiv", f"https://arxiv.org/abs/{arxiv}")
        metadata_changed |= upsert_link(item, "PDF", get(f, "New PDF URL / 新 PDF 連結"))
        metadata_changed |= upsert_link(item, "DOI", get(f, "New DOI URL / 新 DOI 連結"))
        metadata_changed |= upsert_link(item, "Journal", get(f, "New journal page URL / 新期刊頁面連結"))
        metadata_changed |= upsert_link(item, "Code", get(f, "New code URL / 新程式碼連結"))
        group = resolve_publication_group(data, f, item, edit=True, metadata_changed=metadata_changed)
        item["group_id"] = group["id"]
        if old_group != group["id"]:
            item["order"] = next_order(data, "publication", group["id"])
        normalize_orders(data, "publication")
        cleanup_empty_groups(data)
    return entry_id


def cleanup_empty_groups(data: dict[str, Any]) -> None:
    for kind, section in (("publication", "publications"), ("teaching", "teaching")):
        used = {str(x.get("group_id") or "") for x in data.get(section, [])}
        kept = [g for g in content_groups(data, kind) if g.get("id") in used or (kind == "publication" and g.get("preset"))]
        data.setdefault("settings", {}).setdefault("content_groups", {})[kind] = kept
        normalize_orders(data, kind)


def remove_entry(data: dict[str, Any], f: dict[str, str]) -> str:
    entry_id = get(f, "Entry ID / 項目 ID", True)
    section, existing = locate(data, entry_id)
    kind = str(existing.get("type") or "")
    data[section] = [x for x in data[section] if x.get("id") != entry_id]
    cleanup_empty_groups(data)
    if kind in UNGROUPED_KINDS:
        sync_ungrouped_order(data, kind)
    return entry_id


def parse_ordering_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json|javascript|js)?\s*(.*?)\s*```", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Ordering payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Ordering payload must be one JSON object.")
    return payload


def reorder_entries(data: dict[str, Any], f: dict[str, str]) -> str:
    payload = parse_ordering_payload(get(f, "Ordering payload / 排序資料", True))
    kind = str(payload.get("kind") or "").strip().casefold()
    if kind not in SORTABLE_KINDS:
        raise ValueError(f"Unsupported ordering kind: {kind}")
    if kind in UNGROUPED_KINDS:
        ids = [str(x) for x in payload.get("entries", [])]
        current = {str(x.get("id")) for x in entries_of_kind(data, kind)}
        if len(ids) != len(set(ids)) or set(ids) != current:
            raise ValueError(f"{kind} ordering must contain every Entry ID exactly once.")
        data.setdefault("settings", {}).setdefault("entry_order", {})[kind] = ids
        mark_manually_ordered(data, kind)
        return f"reorder-{kind}"
    section = "publications" if kind == "publication" else "teaching"
    rows = payload.get("groups")
    if not isinstance(rows, list):
        raise ValueError("Grouped ordering requires a groups array.")
    existing_groups = {str(g.get("id")): g for g in content_groups(data, kind)}
    by_id = {str(x.get("id")): x for x in data.get(section, [])}
    seen_groups: set[str] = set()
    seen_entries: set[str] = set()
    for group_order, row in enumerate(rows):
        gid = str((row or {}).get("id") or "")
        if gid not in existing_groups or gid in seen_groups:
            raise ValueError(f"Unknown or duplicate group ID: {gid}")
        seen_groups.add(gid)
        existing_groups[gid]["order"] = group_order
        for entry_order, entry_id in enumerate((row or {}).get("entries", [])):
            entry_id = str(entry_id)
            if entry_id not in by_id or entry_id in seen_entries:
                raise ValueError(f"Unknown or duplicate Entry ID: {entry_id}")
            seen_entries.add(entry_id)
            by_id[entry_id]["group_id"] = gid
            by_id[entry_id]["order"] = entry_order
    if seen_entries != set(by_id):
        raise ValueError(f"Ordering must include every {kind} Entry ID.")
    cleanup_empty_groups(data)
    normalize_orders(data, kind)
    return f"reorder-{kind}"


def process(title: str, fields: dict[str, str], data: dict[str, Any]) -> tuple[str, str]:
    migrate_data(data)
    handlers = [
        ("[Website: Add conference]", "Added conference", add_conference),
        ("[Website: Add talk]", "Added talk", add_talk),
        ("[Website: Add visit]", "Added academic visit", add_visit),
        ("[Website: Add honor]", "Added honor", add_honor),
        ("[Website: Add publication]", "Added publication", add_publication),
        ("[Website: Add teaching]", "Added teaching course", add_teaching),
        ("[Website: Edit]", "Edited entry", edit_entry),
        ("[Website: Remove]", "Removed entry", remove_entry),
        ("[Website: Reorder]", "Reordered website entries", reorder_entries),
    ]
    for prefix, action, handler in handlers:
        if title.startswith(prefix):
            return action, handler(data, fields)
    raise ValueError("This issue is not a recognized website form.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_file", type=Path)
    parser.add_argument("--result-file", type=Path)
    args = parser.parse_args()
    event = json.loads(args.event_file.read_text(encoding="utf-8"))
    issue = event["issue"]
    fields = parse_form(issue.get("body", ""))
    data = load_data()
    action, entry_id = process(issue.get("title", ""), fields, data)
    save_data(data)
    result = {"action": action, "entry_id": entry_id, "notes": NOTES, "warnings": WARNINGS}
    if args.result_file:
        args.result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
