#!/usr/bin/env python3
"""Process a GitHub Issue Form and update content/site.json.

This script is designed for GitHub Actions. It uses only Python's standard
library and never changes HTML directly; build_site.py performs rendering.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"
WARNINGS: list[str] = []
NOTES: list[str] = []



def load_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data: dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_label(label: str) -> str:
    label = re.sub(r"\s*[\[（(](?:必填|選填|required|optional|選填・可自動翻譯)[\]）)]", "", label, flags=re.I)
    label = label.replace(" [選填・可自動翻譯]", "").strip()
    return re.sub(r"\s+", " ", label)


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
    return value.strip().lower().startswith(("yes", "是"))



def auto_chinese(fields: dict[str, str]) -> bool:
    mode = get(fields, "Chinese handling / 中文欄位處理")
    return not mode or mode.startswith("Auto") or "自動翻譯" in mode


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if any(ch.isspace() for ch in value):
        raise ValueError(f"URL cannot contain spaces: {value}")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.I):
        value = "https://" + value.lstrip("/")
    return value


def normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", strip_markup(value).lower())


def ensure_not_duplicate(data: dict[str, Any], kind: str, anchor: str, title: str) -> None:
    key = normalized_text(title)
    for item in data.get("activities", []) + data.get("honors", []) + data.get("publications", []) + data.get("teaching", []):
        if item.get("type") != kind:
            continue
        old_anchor = str(item.get("start_date") or item.get("date") or item.get("year") or "")
        old_title = ((item.get("title") or item.get("course") or {}).get("en") or "")
        if old_anchor == anchor and normalized_text(old_title) == key:
            raise ValueError(f"Possible duplicate: {kind} on {anchor} with the same English title already exists (Entry ID: {item.get('id')}).")


def collect_memory(data: dict[str, Any]) -> dict[str, str]:
    memory: dict[str, str] = {}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            en, zh = value.get("en"), value.get("zh")
            if isinstance(en, str) and isinstance(zh, str) and en.strip() and zh.strip():
                memory[en.strip().casefold()] = zh.strip()
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data)
    return memory


STATIC_TRANSLATIONS = {
    "japan": "日本", "taiwan": "臺灣", "united states": "美國", "usa": "美國",
    "tokyo": "東京", "sendai": "仙台", "nagoya": "名古屋", "nagasaki": "長崎",
    "tohoku university": "東北大學", "nagoya university": "名古屋大學",
    "national tsing hua university": "國立清華大學",
    "japan–taiwan exchange association": "日本台灣交流協會",
    "japan-taiwan exchange association": "日本台灣交流協會",
    "supported by the japan–taiwan exchange association": "獲日本台灣交流協會補助",
    "supported by the japan-taiwan exchange association": "獲日本台灣交流協會補助",
    "spring": "春", "fall": "秋", "autumn": "秋",
}


def history_examples(data: dict[str, Any], kind: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sections = [data.get("activities", []), data.get("honors", []), data.get("publications", []), data.get("teaching", [])]
    for item in sum(sections, []):
        if kind and item.get("type") != kind:
            continue
        for key in ("title", "description", "organization", "venue", "term", "course", "authors"):
            pair = item.get(key) or {}
            if isinstance(pair, dict) and pair.get("en") and pair.get("zh"):
                rows.append({"field": key, "en": str(pair["en"]), "zh": str(pair["zh"])})
    return rows[-30:]


def call_github_model(requests: dict[str, str], data: dict[str, Any], kind: str) -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token or not requests:
        return {}
    model = os.environ.get("TRANSLATION_MODEL", "openai/gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You translate metadata for a Taiwanese mathematician's academic website into natural Traditional Chinese used in Taiwan. "
                    "Reuse the exact terminology and naming style in the historical examples whenever the same institution, city, event series, course, award, or journal occurs. "
                    "Preserve mathematical notation, HTML-like [i] and [b] markers, acronyms, arXiv identifiers, and URLs. "
                    "For personal names, use a known Chinese form only if supported by the examples; otherwise keep the Latin-script name. "
                    "Return only one valid JSON object whose keys exactly match the requested keys and whose values are strings."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"type": kind, "historical_examples": history_examples(data, kind), "translate": requests}, ensure_ascii=False),
            },
        ],
    }
    req = urllib.request.Request(
        "https://models.github.ai/inference/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        match = re.search(r"\{.*\}", content, flags=re.S)
        parsed = json.loads(match.group(0) if match else content)
        return {k: str(v).strip() for k, v in parsed.items() if k in requests and str(v).strip()}
    except Exception as exc:
        WARNINGS.append(f"GitHub Models 暫時無法使用（{type(exc).__name__}），已改用保守 fallback。")
        return {}


FIELD_LABELS = {
    "title": "名稱／題目", "venue": "場地", "city": "城市", "country": "國家",
    "event": "活動名稱", "institution": "機構", "funding": "補助說明",
    "organization": "頒發單位", "authors": "作者", "term": "學期",
    "course": "課程", "description": "說明",
}


def series_translation(data: dict[str, Any], kind: str, english: str) -> str:
    """Reuse a previous bilingual series title while replacing edition numbers."""
    def signature(value: str) -> str:
        value = strip_markup(value).casefold()
        value = re.sub(r"\bthe\b", " ", value)
        value = re.sub(r"\b\d+(?:st|nd|rd|th)?\b", "#", value)
        return re.sub(r"[^a-z#]+", " ", value).strip()
    current_sig = signature(english)
    current_numbers = re.findall(r"\d+", english)
    if not current_sig or not current_numbers:
        return ""
    for item in data.get("activities", []):
        if item.get("type") != kind:
            continue
        pair = item.get("title") or {}
        old_en, old_zh = str(pair.get("en") or ""), str(pair.get("zh") or "")
        if old_en and old_zh and signature(old_en) == current_sig:
            old_numbers = re.findall(r"\d+", old_en)
            result = old_zh
            for old, new in zip(old_numbers, current_numbers):
                result = re.sub(rf"(?<!\d){re.escape(old)}(?!\d)", new, result, count=1)
            return result
    return ""


def fill_chinese(data: dict[str, Any], kind: str, fields: dict[str, str], pairs: dict[str, tuple[str, str]]) -> dict[str, str]:
    memory = collect_memory(data)
    resolved: dict[str, str] = {}
    unresolved: dict[str, str] = {}
    use_auto = auto_chinese(fields)
    for key, (en, zh) in pairs.items():
        en, zh = en.strip(), zh.strip()
        if zh:
            resolved[key] = zh
        elif not en:
            resolved[key] = ""
        elif not use_auto:
            raise ValueError(f"Chinese field is blank while manual Chinese mode is selected: {key}")
        elif key == "title" and series_translation(data, kind, en):
            resolved[key] = series_translation(data, kind, en)
            NOTES.append(f"沿用同系列活動的中文格式：{resolved[key]}")
        elif en.casefold() in memory:
            resolved[key] = memory[en.casefold()]
            NOTES.append(f"沿用既有{FIELD_LABELS.get(key, key)}譯名：{resolved[key]}")
        elif en.casefold() in STATIC_TRANSLATIONS:
            resolved[key] = STATIC_TRANSLATIONS[en.casefold()]
            NOTES.append(f"使用既有詞彙表翻譯{FIELD_LABELS.get(key, key)}：{resolved[key]}")
        else:
            unresolved[key] = en
    generated = call_github_model(unresolved, data, kind)
    for key, en in unresolved.items():
        if generated.get(key):
            resolved[key] = generated[key]
            NOTES.append(f"AI 自動翻譯{FIELD_LABELS.get(key, key)}：{generated[key]}")
        else:
            resolved[key] = en
            WARNINGS.append(f"無法可靠翻譯{FIELD_LABELS.get(key, key)}，中文版暫時保留英文。")
    return resolved


def strip_markup(value: str) -> str:
    return re.sub(r"\[/?(?:i|b)\]", "", value, flags=re.I).strip()


def limited_markup(value: str) -> str:
    """Escape text, then allow only [i]...[/i] and [b]...[/b]."""
    out = html.escape(value.strip(), quote=False)
    out = re.sub(r"\[i\](.+?)\[/i\]", r"<em>\1</em>", out, flags=re.I | re.S)
    out = re.sub(r"\[b\](.+?)\[/b\]", r"<strong>\1</strong>", out, flags=re.I | re.S)
    return out


def mark_self(value: str, lang: str) -> str:
    escaped = limited_markup(value)
    name = "崔鴻竣" if lang == "zh" else "Hung-Chun Tsui"
    escaped_name = html.escape(name)
    if f"<strong>{escaped_name}</strong>" not in escaped:
        escaped = escaped.replace(escaped_name, f"<strong>{escaped_name}</strong>")
    return escaped


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:46] or "entry"


def unique_id(data: dict[str, Any], kind: str, anchor: str, title: str) -> str:
    existing = {
        item["id"]
        for section in ("activities", "honors", "publications", "teaching")
        for item in data.get(section, [])
    }
    base = f"{kind}-{anchor}-{slug(title)}".strip("-")
    if base not in existing:
        return base
    digest = hashlib.sha1(f"{kind}|{anchor}|{title}|{len(existing)}".encode()).hexdigest()[:7]
    return f"{base}-{digest}"


def location(*parts: str) -> str:
    return ", ".join(part.strip() for part in parts if part.strip())


def add_conference(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Start date / 開始日期", True), "Start date")
    end = iso(get(f, "End date / 結束日期") or start, "End date")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")
    title_en = get(f, "Conference name (English) / 會議英文名稱", True)
    ensure_not_duplicate(data, "conference", start, title_en)
    translated = fill_chinese(data, "conference", f, {
        "title": (title_en, get(f, "Conference name (Chinese) / 會議中文名稱")),
        "venue": (get(f, "Venue (English) / 地點英文"), get(f, "Venue (Chinese) / 地點中文")),
        "city": (get(f, "City (English) / 城市英文"), get(f, "City (Chinese) / 城市中文")),
        "country": (get(f, "Country (English) / 國家英文"), get(f, "Country (Chinese) / 國家中文")),
    })
    entry = {
        "id": unique_id(data, "conference", start, strip_markup(title_en)), "type": "conference",
        "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(translated["title"])},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(translated["title"])},
        "url": normalize_url(get(f, "Conference URL / 會議連結")),
        "description": {
            "en": location(get(f, "Venue (English) / 地點英文"), get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文")),
            "zh": location(translated["venue"], translated["city"], translated["country"]),
        }, "description_html": {}, "slides_url": "",
    }
    entry["description_html"] = {k: limited_markup(v) for k, v in entry["description"].items()}
    data["activities"].append(entry)
    return entry["id"]


def add_talk(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Talk date / 演講日期", True), "Talk date")
    end = iso(get(f, "End date (optional) / 結束日期（選填）") or get(f, "End date (optional) / 結束日期") or start, "End date")
    title_en = get(f, "Talk title (English) / 演講英文題目", True)
    ensure_not_duplicate(data, "talk", start, title_en)
    translated = fill_chinese(data, "talk", f, {
        "title": (title_en, get(f, "Talk title (Chinese) / 演講中文題目")),
        "event": (get(f, "Event (English) / 活動英文名稱"), get(f, "Event (Chinese) / 活動中文名稱")),
        "institution": (get(f, "Institution (English) / 機構英文"), get(f, "Institution (Chinese) / 機構中文")),
        "city": (get(f, "City (English) / 城市英文"), get(f, "City (Chinese) / 城市中文")),
        "country": (get(f, "Country (English) / 國家英文"), get(f, "Country (Chinese) / 國家中文")),
    })
    entry = {
        "id": unique_id(data, "talk", start, strip_markup(title_en)), "type": "talk",
        "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(translated["title"])},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(translated["title"])},
        "url": normalize_url(get(f, "Talk or event URL / 演講或活動連結")),
        "description": {
            "en": location(get(f, "Event (English) / 活動英文名稱"), get(f, "Institution (English) / 機構英文"), get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文")),
            "zh": location(translated["event"], translated["institution"], translated["city"], translated["country"]),
        }, "description_html": {},
        "slides_url": normalize_url(get(f, "Slides URL / 投影片連結")),
    }
    entry["description_html"] = {k: limited_markup(v) for k, v in entry["description"].items()}
    data["activities"].append(entry)
    return entry["id"]


def add_visit(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Start date / 開始日期", True), "Start date")
    end = iso(get(f, "End date / 結束日期") or start, "End date")
    institution_en = get(f, "Institution (English) / 機構英文", True)
    ensure_not_duplicate(data, "visit", start, institution_en)
    translated = fill_chinese(data, "visit", f, {
        "institution": (institution_en, get(f, "Institution (Chinese) / 機構中文")),
        "city": (get(f, "City (English) / 城市英文"), get(f, "City (Chinese) / 城市中文")),
        "country": (get(f, "Country (English) / 國家英文"), get(f, "Country (Chinese) / 國家中文")),
        "funding": (get(f, "Funding note (English) / 補助說明英文"), get(f, "Funding note (Chinese) / 補助說明中文")),
    })
    base_en = location(get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文"))
    base_zh = location(translated["city"], translated["country"])
    support_en, support_zh = get(f, "Funding note (English) / 補助說明英文"), translated["funding"]
    desc_en = f"{base_en} · {support_en}" if base_en and support_en else (base_en or support_en)
    desc_zh = f"{base_zh} · {support_zh}" if base_zh and support_zh else (base_zh or support_zh)
    entry = {
        "id": unique_id(data, "visit", start, strip_markup(institution_en)), "type": "visit",
        "start_date": start, "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(institution_en), "zh": strip_markup(translated["institution"])},
        "title_html": {"en": limited_markup(institution_en), "zh": limited_markup(translated["institution"])},
        "url": normalize_url(get(f, "Institution or visit URL / 機構或訪問連結")),
        "description": {"en": desc_en, "zh": desc_zh},
        "description_html": {"en": limited_markup(desc_en), "zh": limited_markup(desc_zh)}, "slides_url": "",
    }
    data["activities"].append(entry)
    return entry["id"]


def add_honor(data: dict[str, Any], f: dict[str, str]) -> str:
    year_text = get(f, "Year / 年份", True)
    if not re.fullmatch(r"\d{4}", year_text): raise ValueError("Year must contain four digits.")
    name_en = get(f, "Honor name (English) / 獎項英文名稱", True)
    ensure_not_duplicate(data, "honor", year_text, name_en)
    translated = fill_chinese(data, "honor", f, {
        "title": (name_en, get(f, "Honor name (Chinese) / 獎項中文名稱")),
        "organization": (get(f, "Organization (English) / 頒發單位英文"), get(f, "Organization (Chinese) / 頒發單位中文")),
    })
    for item in [x for x in data["honors"] if int(x.get("year", 0)) == int(year_text)]: item["order"] = int(item.get("order", 0)) + 1
    entry = {
        "id": unique_id(data, "honor", year_text, strip_markup(name_en)), "type": "honor", "year": int(year_text), "order": 0,
        "title": {"en": strip_markup(name_en), "zh": strip_markup(translated["title"])},
        "title_html": {"en": limited_markup(name_en), "zh": limited_markup(translated["title"])},
        "url": normalize_url(get(f, "Honor URL / 獎項連結")),
        "organization": {"en": get(f, "Organization (English) / 頒發單位英文"), "zh": translated["organization"]}, "organization_html": {},
    }
    entry["organization_html"] = {k: limited_markup(v) for k, v in entry["organization"].items()}
    data["honors"].append(entry)
    return entry["id"]


def add_publication(data: dict[str, Any], f: dict[str, str]) -> str:
    pub_date = iso(get(f, "Public date / 公開日期", True), "Public date")
    title_en, authors_en = get(f, "Title (English) / 英文題目", True), get(f, "Authors (English) / 作者英文", True)
    ensure_not_duplicate(data, "publication", pub_date, title_en)
    translated = fill_chinese(data, "publication", f, {
        "title": (title_en, get(f, "Title (Chinese) / 中文題目")),
        "authors": (authors_en, get(f, "Authors (Chinese) / 作者中文")),
        "venue": (get(f, "Venue or status (English) / 期刊或狀態英文"), get(f, "Venue or status (Chinese) / 期刊或狀態中文")),
    })
    arxiv = get(f, "arXiv number / arXiv 編號")
    venue_en = get(f, "Venue or status (English) / 期刊或狀態英文") or (f"arXiv:{arxiv}" if arxiv else "")
    venue_zh = translated["venue"] or (f"arXiv:{arxiv}" if arxiv else venue_en)
    links = []
    candidates = [
        ("arXiv", get(f, "arXiv URL / arXiv 連結") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")),
        ("PDF", get(f, "PDF URL / PDF 連結")), ("DOI", get(f, "DOI URL / DOI 連結")),
        ("Journal", get(f, "Journal page URL / 期刊頁面連結")), ("Code", get(f, "Code URL / 程式碼連結")),
    ]
    for label, url in candidates:
        url = normalize_url(url)
        if url: links.append({"label": {"en": label, "zh": "期刊頁面" if label == "Journal" else "程式碼" if label == "Code" else label}, "url": url})
    order = max([int(x.get("order", -1)) for x in data["publications"]] + [-1]) + 1
    entry = {
        "id": unique_id(data, "publication", arxiv or pub_date, strip_markup(title_en)), "type": "publication", "date": pub_date,
        "year": int(pub_date[:4]), "order": order, "arxiv": arxiv,
        "title": {"en": strip_markup(title_en), "zh": strip_markup(translated["title"])},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(translated["title"])},
        "authors": {"en": strip_markup(authors_en), "zh": strip_markup(translated["authors"])},
        "authors_html": {"en": mark_self(authors_en, "en"), "zh": mark_self(translated["authors"], "zh")},
        "venue": {"en": venue_en, "zh": venue_zh}, "venue_html": {"en": limited_markup(venue_en), "zh": limited_markup(venue_zh)}, "links": links,
    }
    data["publications"].append(entry)
    return entry["id"]


def add_teaching(data: dict[str, Any], f: dict[str, str]) -> str:
    term_en, course_en = get(f, "Term (English) / 學期英文", True), get(f, "Course (English) / 課程英文", True)
    ensure_not_duplicate(data, "teaching", term_en, course_en)
    translated = fill_chinese(data, "teaching", f, {
        "term": (term_en, get(f, "Term (Chinese) / 學期中文")),
        "course": (course_en, get(f, "Course (Chinese) / 課程中文")),
    })
    place_top = yes(get(f, "Place at top? / 是否放在最前面", True))
    if place_top:
        for item in data["teaching"]: item["order"] = int(item.get("order", 0)) + 1
        order = 0
    else: order = max([int(x.get("order", -1)) for x in data["teaching"]] + [-1]) + 1
    entry = {"id": unique_id(data, "teaching", str(order), course_en), "type": "teaching", "order": order,
             "term": {"en": term_en, "zh": translated["term"]}, "course": {"en": course_en, "zh": translated["course"]}}
    data["teaching"].append(entry)
    return entry["id"]

def locate(data: dict[str, Any], entry_id: str) -> tuple[str, dict[str, Any]]:
    for section in ("activities", "honors", "publications", "teaching"):
        for item in data.get(section, []):
            if item.get("id") == entry_id:
                return section, item
    raise ValueError(f"Cannot find entry ID: {entry_id}")


def remove_entry(data: dict[str, Any], f: dict[str, str]) -> str:
    entry_id = get(f, "Entry ID / 項目 ID", True)
    section, _ = locate(data, entry_id)
    data[section] = [x for x in data[section] if x.get("id") != entry_id]
    return entry_id


def edit_entry(data: dict[str, Any], f: dict[str, str]) -> str:
    entry_id = get(f, "Entry ID / 項目 ID", True)
    _, item = locate(data, entry_id)

    en = get(f, "New English title/name/course / 新英文題目、名稱或課名")
    zh = get(f, "New Chinese title/name/course / 新中文題目、名稱或課名")
    if en and not zh:
        zh = fill_chinese(data, item["type"], f, {"title": (en, "")})["title"]
    if item["type"] == "teaching":
        if en: item["course"]["en"] = en
        if zh: item["course"]["zh"] = zh
    else:
        if en:
            item.setdefault("title", {})["en"] = strip_markup(en)
            item.setdefault("title_html", {})["en"] = limited_markup(en)
        if zh:
            item.setdefault("title", {})["zh"] = strip_markup(zh)
            item.setdefault("title_html", {})["zh"] = limited_markup(zh)

    start = get(f, "New start/public date / 新開始或公開日期")
    end = get(f, "New end date / 新結束日期")
    year = get(f, "New year / 新年份")
    if start:
        start = iso(start, "New date")
        if item["type"] == "publication":
            item["date"] = start
            item["year"] = int(start[:4])
        else:
            item["start_date"] = start
    if end and item["type"] in {"conference", "talk", "visit"}:
        item["end_date"] = iso(end, "New end date")
    if year and item["type"] == "honor":
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError("New year must contain four digits.")
        item["year"] = int(year)

    new_url = get(f, "New main URL / 新主要連結")
    if new_url:
        item["url"] = normalize_url(new_url)

    desc_en = get(f, "New English description/organization/term / 新英文說明、單位或學期")
    desc_zh = get(f, "New Chinese description/organization/term / 新中文說明、單位或學期")
    if desc_en and not desc_zh:
        desc_zh = fill_chinese(data, item["type"], f, {"description": (desc_en, "")})["description"]
    if item["type"] in {"conference", "talk", "visit"}:
        for lang, value in (("en", desc_en), ("zh", desc_zh)):
            if value:
                item.setdefault("description", {})[lang] = value
                item.setdefault("description_html", {})[lang] = limited_markup(value)
    elif item["type"] == "honor":
        for lang, value in (("en", desc_en), ("zh", desc_zh)):
            if value:
                item.setdefault("organization", {})[lang] = value
                item.setdefault("organization_html", {})[lang] = limited_markup(value)
    elif item["type"] == "teaching":
        if desc_en: item.setdefault("term", {})["en"] = desc_en
        if desc_zh: item.setdefault("term", {})["zh"] = desc_zh
    elif item["type"] == "publication":
        for lang, value in (("en", desc_en), ("zh", desc_zh)):
            if value:
                item.setdefault("venue", {})[lang] = value
                item.setdefault("venue_html", {})[lang] = limited_markup(value)

    authors_en = get(f, "New authors (English) / 新作者英文")
    authors_zh = get(f, "New authors (Chinese) / 新作者中文")
    if authors_en and not authors_zh:
        authors_zh = fill_chinese(data, "publication", f, {"authors": (authors_en, "")})["authors"]
    if item["type"] == "publication":
        if authors_en:
            item.setdefault("authors", {})["en"] = authors_en
            item.setdefault("authors_html", {})["en"] = mark_self(authors_en, "en")
        if authors_zh:
            item.setdefault("authors", {})["zh"] = authors_zh
            item.setdefault("authors_html", {})["zh"] = mark_self(authors_zh, "zh")

    auxiliary = get(f, "New slides or PDF URL / 新投影片或 PDF 連結")
    if auxiliary:
        if item["type"] == "talk":
            item["slides_url"] = normalize_url(auxiliary)
        elif item["type"] == "publication":
            links = [x for x in item.get("links", []) if (x.get("label") or {}).get("en") != "PDF"]
            links.append({"label": {"en": "PDF", "zh": "PDF"}, "url": normalize_url(auxiliary)})
            item["links"] = links

    upcoming = get(f, "Upcoming setting / Upcoming 設定")
    if item["type"] in {"conference", "talk", "visit"} and upcoming:
        if upcoming.startswith("Yes") or upcoming.startswith("是"):
            item["show_upcoming"] = True
        elif upcoming.startswith("No") or upcoming.startswith("否"):
            item["show_upcoming"] = False

    return entry_id


def process(title: str, fields: dict[str, str], data: dict[str, Any]) -> tuple[str, str]:
    if title.startswith("[Website: Add conference]"):
        return "Added conference", add_conference(data, fields)
    if title.startswith("[Website: Add talk]"):
        return "Added talk", add_talk(data, fields)
    if title.startswith("[Website: Add visit]"):
        return "Added academic visit", add_visit(data, fields)
    if title.startswith("[Website: Add honor]"):
        return "Added honor", add_honor(data, fields)
    if title.startswith("[Website: Add publication]"):
        return "Added publication", add_publication(data, fields)
    if title.startswith("[Website: Add teaching]"):
        return "Added teaching course", add_teaching(data, fields)
    if title.startswith("[Website: Edit]"):
        return "Edited entry", edit_entry(data, fields)
    if title.startswith("[Website: Remove]"):
        return "Removed entry", remove_entry(data, fields)
    raise ValueError("This issue is not a recognized website form.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event_file", type=Path)
    parser.add_argument("--result-file", type=Path)
    args = parser.parse_args()
    event = json.loads(args.event_file.read_text(encoding="utf-8"))
    issue = event["issue"]
    title = issue.get("title", "")
    fields = parse_form(issue.get("body", ""))
    data = load_data()
    action, entry_id = process(title, fields, data)
    save_data(data)
    result = {"action": action, "entry_id": entry_id, "notes": NOTES, "warnings": WARNINGS}
    if args.result_file:
        args.result_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
