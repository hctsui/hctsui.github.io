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
import re
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "content" / "site.json"


def load_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_data(data: dict[str, Any]) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_form(body: str) -> dict[str, str]:
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for raw in body.splitlines():
        if raw.startswith("### "):
            current = raw[4:].strip()
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
    end_raw = get(f, "End date / 結束日期") or start
    end = iso(end_raw, "End date")
    if end < start:
        raise ValueError("End date cannot be earlier than start date.")
    title_en = get(f, "Conference name (English) / 會議英文名稱", True)
    title_zh = get(f, "Conference name (Chinese) / 會議中文名稱", True)
    entry = {
        "id": unique_id(data, "conference", start, strip_markup(title_en)),
        "type": "conference",
        "start_date": start,
        "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "url": get(f, "Conference URL / 會議連結"),
        "description": {
            "en": location(get(f, "Venue (English) / 地點英文"), get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文")),
            "zh": location(get(f, "Venue (Chinese) / 地點中文"), get(f, "City (Chinese) / 城市中文"), get(f, "Country (Chinese) / 國家中文")),
        },
        "description_html": {},
        "slides_url": "",
    }
    entry["description_html"] = {k: limited_markup(v) for k, v in entry["description"].items()}
    data["activities"].append(entry)
    return entry["id"]


def add_talk(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Talk date / 演講日期", True), "Talk date")
    end_raw = get(f, "End date (optional) / 結束日期（選填）") or start
    end = iso(end_raw, "End date")
    title_en = get(f, "Talk title (English) / 演講英文題目", True)
    title_zh = get(f, "Talk title (Chinese) / 演講中文題目", True)
    entry = {
        "id": unique_id(data, "talk", start, strip_markup(title_en)),
        "type": "talk",
        "start_date": start,
        "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "url": get(f, "Talk or event URL / 演講或活動連結"),
        "description": {
            "en": location(get(f, "Event (English) / 活動英文名稱"), get(f, "Institution (English) / 機構英文"), get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文")),
            "zh": location(get(f, "Event (Chinese) / 活動中文名稱"), get(f, "Institution (Chinese) / 機構中文"), get(f, "City (Chinese) / 城市中文"), get(f, "Country (Chinese) / 國家中文")),
        },
        "description_html": {},
        "slides_url": get(f, "Slides URL / 投影片連結"),
    }
    entry["description_html"] = {k: limited_markup(v) for k, v in entry["description"].items()}
    data["activities"].append(entry)
    return entry["id"]


def add_visit(data: dict[str, Any], f: dict[str, str]) -> str:
    start = iso(get(f, "Start date / 開始日期", True), "Start date")
    end = iso(get(f, "End date / 結束日期", True), "End date")
    institution_en = get(f, "Institution (English) / 機構英文", True)
    institution_zh = get(f, "Institution (Chinese) / 機構中文", True)
    base_en = location(get(f, "City (English) / 城市英文"), get(f, "Country (English) / 國家英文"))
    base_zh = location(get(f, "City (Chinese) / 城市中文"), get(f, "Country (Chinese) / 國家中文"))
    support_en = get(f, "Funding note (English) / 補助說明英文")
    support_zh = get(f, "Funding note (Chinese) / 補助說明中文")
    desc_en = f"{base_en} · {support_en}" if base_en and support_en else (base_en or support_en)
    desc_zh = f"{base_zh} · {support_zh}" if base_zh and support_zh else (base_zh or support_zh)
    entry = {
        "id": unique_id(data, "visit", start, strip_markup(institution_en)),
        "type": "visit",
        "start_date": start,
        "end_date": end,
        "show_upcoming": yes(get(f, "Show on Upcoming? / 是否先顯示於 Upcoming", True)),
        "title": {"en": strip_markup(institution_en), "zh": strip_markup(institution_zh)},
        "title_html": {"en": limited_markup(institution_en), "zh": limited_markup(institution_zh)},
        "url": get(f, "Institution or visit URL / 機構或訪問連結"),
        "description": {"en": desc_en, "zh": desc_zh},
        "description_html": {"en": limited_markup(desc_en), "zh": limited_markup(desc_zh)},
        "slides_url": "",
    }
    data["activities"].append(entry)
    return entry["id"]


def add_honor(data: dict[str, Any], f: dict[str, str]) -> str:
    year_text = get(f, "Year / 年份", True)
    if not re.fullmatch(r"\d{4}", year_text):
        raise ValueError("Year must contain four digits.")
    name_en = get(f, "Honor name (English) / 獎項英文名稱", True)
    name_zh = get(f, "Honor name (Chinese) / 獎項中文名稱", True)
    same_year = [x for x in data["honors"] if int(x.get("year", 0)) == int(year_text)]
    for item in same_year:
        item["order"] = int(item.get("order", 0)) + 1
    entry = {
        "id": unique_id(data, "honor", year_text, strip_markup(name_en)),
        "type": "honor",
        "year": int(year_text),
        "order": 0,
        "title": {"en": strip_markup(name_en), "zh": strip_markup(name_zh)},
        "title_html": {"en": limited_markup(name_en), "zh": limited_markup(name_zh)},
        "url": get(f, "Honor URL / 獎項連結"),
        "organization": {
            "en": get(f, "Organization (English) / 頒發單位英文"),
            "zh": get(f, "Organization (Chinese) / 頒發單位中文"),
        },
        "organization_html": {},
    }
    entry["organization_html"] = {k: limited_markup(v) for k, v in entry["organization"].items()}
    data["honors"].append(entry)
    return entry["id"]


def add_publication(data: dict[str, Any], f: dict[str, str]) -> str:
    pub_date = iso(get(f, "Public date / 公開日期", True), "Public date")
    title_en = get(f, "Title (English) / 英文題目", True)
    title_zh = get(f, "Title (Chinese) / 中文題目", True)
    authors_en = get(f, "Authors (English) / 作者英文", True)
    authors_zh = get(f, "Authors (Chinese) / 作者中文", True)
    arxiv = get(f, "arXiv number / arXiv 編號")
    venue_en = get(f, "Venue or status (English) / 期刊或狀態英文") or (f"arXiv:{arxiv}" if arxiv else "")
    venue_zh = get(f, "Venue or status (Chinese) / 期刊或狀態中文") or (f"arXiv:{arxiv}" if arxiv else venue_en)
    links = []
    arxiv_url = get(f, "arXiv URL / arXiv 連結") or (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")
    if arxiv_url:
        links.append({"label": {"en": "arXiv", "zh": "arXiv"}, "url": arxiv_url})
    pdf_url = get(f, "PDF URL / PDF 連結")
    if pdf_url:
        links.append({"label": {"en": "PDF", "zh": "PDF"}, "url": pdf_url})
    order = max([int(x.get("order", -1)) for x in data["publications"]] + [-1]) + 1
    entry = {
        "id": unique_id(data, "publication", arxiv or pub_date, strip_markup(title_en)),
        "type": "publication",
        "date": pub_date,
        "year": int(pub_date[:4]),
        "order": order,
        "arxiv": arxiv,
        "title": {"en": strip_markup(title_en), "zh": strip_markup(title_zh)},
        "title_html": {"en": limited_markup(title_en), "zh": limited_markup(title_zh)},
        "authors": {"en": strip_markup(authors_en), "zh": strip_markup(authors_zh)},
        "authors_html": {"en": mark_self(authors_en, "en"), "zh": mark_self(authors_zh, "zh")},
        "venue": {"en": venue_en, "zh": venue_zh},
        "venue_html": {"en": limited_markup(venue_en), "zh": limited_markup(venue_zh)},
        "links": links,
    }
    data["publications"].append(entry)
    return entry["id"]


def add_teaching(data: dict[str, Any], f: dict[str, str]) -> str:
    term_en = get(f, "Term (English) / 學期英文", True)
    term_zh = get(f, "Term (Chinese) / 學期中文", True)
    course_en = get(f, "Course (English) / 課程英文", True)
    course_zh = get(f, "Course (Chinese) / 課程中文", True)
    place_top = yes(get(f, "Place at top? / 是否放在最前面", True))
    if place_top:
        for item in data["teaching"]:
            item["order"] = int(item.get("order", 0)) + 1
        order = 0
    else:
        order = max([int(x.get("order", -1)) for x in data["teaching"]] + [-1]) + 1
    entry = {
        "id": unique_id(data, "teaching", str(order), course_en),
        "type": "teaching",
        "order": order,
        "term": {"en": term_en, "zh": term_zh},
        "course": {"en": course_en, "zh": course_zh},
    }
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
        item["url"] = new_url

    desc_en = get(f, "New English description/organization/term / 新英文說明、單位或學期")
    desc_zh = get(f, "New Chinese description/organization/term / 新中文說明、單位或學期")
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
            item["slides_url"] = auxiliary
        elif item["type"] == "publication":
            links = [x for x in item.get("links", []) if (x.get("label") or {}).get("en") != "PDF"]
            links.append({"label": {"en": "PDF", "zh": "PDF"}, "url": auxiliary})
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
    result = {"action": action, "entry_id": entry_id}
    if args.result_file:
        args.result_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
