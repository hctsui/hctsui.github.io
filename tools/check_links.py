#!/usr/bin/env python3
"""Check managed external links and create actionable Admin notifications for confirmed 404/410 responses."""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from notification_store import normalized_store, resolve_key, upsert, validate_store

ROOT = Path(__file__).resolve().parents[1]
SITE_FILE = ROOT / "content" / "site.json"
PEOPLE_FILE = ROOT / "content" / "people.json"
STORE_FILE = ROOT / "content" / "notifications.json"
BROKEN = {404, 410}
REACHABLE = set(range(200, 400)) | {401, 403, 405, 429}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_http(value: Any) -> bool:
    return str(value or "").strip().lower().startswith(("http://", "https://"))


def label_of(entry: dict[str, Any]) -> str:
    for field in ("title", "course", "name", "description"):
        value = entry.get(field)
        if isinstance(value, dict):
            text = value.get("zh") or value.get("en")
        else:
            text = value
        if text:
            return str(text).strip()[:160]
    return str(entry.get("id") or "未命名項目")


def iter_entry_urls(entry: dict[str, Any], target_type: str) -> Iterable[dict[str, str]]:
    entry_id = str(entry.get("id") or "")
    label = label_of(entry)
    for field, value in entry.items():
        if field in {"url", "arxiv_url", "pdf_url", "doi_url", "journal_url", "code_url", "slides_url", "lecture_notes_url"} or field.endswith("_url"):
            if is_http(value):
                yield {"url": str(value).strip(), "target_type": target_type, "entry_id": entry_id, "field": field, "label": label}
    for index, link in enumerate(entry.get("links", []) if isinstance(entry.get("links"), list) else []):
        if isinstance(link, dict) and is_http(link.get("url")):
            yield {"url": str(link["url"]).strip(), "target_type": target_type, "entry_id": entry_id, "field": f"links[{index}].url", "label": label}


def collect_links(site: dict[str, Any], people: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in site.get("publications", []):
        if isinstance(entry, dict):
            rows.extend(iter_entry_urls(entry, "publication"))
    for entry in site.get("items", []):
        if isinstance(entry, dict):
            rows.extend(iter_entry_urls(entry, str(entry.get("type") or "item")))
    for person in people.get("people", []) if isinstance(people, dict) else []:
        if isinstance(person, dict) and is_http(person.get("url")):
            rows.append({
                "url": str(person["url"]).strip(),
                "target_type": "person",
                "entry_id": str(person.get("id") or ""),
                "field": "url",
                "label": str((person.get("name") or {}).get("zh") or (person.get("name") or {}).get("en") or person.get("id") or "人物"),
            })
    footer = site.get("settings", {}).get("footer", {})
    for item in footer.get("items", []) if isinstance(footer, dict) else []:
        if isinstance(item, dict) and is_http(item.get("url")):
            rows.append({"url": str(item["url"]).strip(), "target_type": "site_settings", "entry_id": "footer", "field": str(item.get("id") or "footer"), "label": "頁尾"})
    unique: dict[str, dict[str, str]] = {}
    for row in rows:
        unique[f"{row['target_type']}:{row['entry_id']}:{row['field']}:{row['url']}"] = row
    return list(unique.values())


def check_url(url: str, timeout: int = 15) -> tuple[str, int | None, str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; hctsui.github.io link checker; +https://hctsui.github.io)"}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, headers={**headers, **({"Range": "bytes=0-0"} if method == "GET" else {})}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = int(getattr(response, "status", 200))
            if status in REACHABLE:
                return "ok", status, ""
            if status in BROKEN:
                return "broken", status, ""
            return "unknown", status, f"HTTP {status}"
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if status in REACHABLE:
                return "ok", status, ""
            if status in BROKEN:
                return "broken", status, str(exc.reason or "")
            if method == "HEAD" and status in {400, 500, 501}:
                continue
            return "unknown", status, str(exc.reason or "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if method == "HEAD":
                continue
            return "unknown", None, str(exc)
    return "unknown", None, "No response"


def notification_for(row: dict[str, str], status: int | None) -> dict[str, Any]:
    key = f"broken-link:{row['target_type']}:{row['entry_id']}:{row['field']}:{row['url']}"
    return {
        "key": key,
        "type": "broken_link",
        "title": f"外部連結失效：{row['label']}",
        "message": f"{row['field']} 回傳 HTTP {status or '錯誤'}：{row['url']}",
        "created_at": now(),
        "updated_at": now(),
        "source_url": row["url"],
        "payload": {**row, "http_status": status},
        "actions": [{"id": "edit", "label": "前往修改"}],
    }


def run(site: dict[str, Any], people: dict[str, Any], store: dict[str, Any], fixture: dict[str, int | str] | None = None) -> tuple[dict[str, Any], int, int]:
    updated = normalized_store(store)
    broken_count = 0
    resolved_count = 0
    active_keys: set[str] = set()
    for row in collect_links(site, people):
        if fixture is not None and row["url"] in fixture:
            raw = fixture[row["url"]]
            status = int(raw) if str(raw).isdigit() else None
            state = "broken" if status in BROKEN else "ok" if status in REACHABLE else "unknown"
        else:
            state, status, _ = check_url(row["url"])
        key = f"broken-link:{row['target_type']}:{row['entry_id']}:{row['field']}:{row['url']}"
        if state == "broken":
            active_keys.add(key)
            updated, changed = upsert(updated, notification_for(row, status))
            broken_count += int(changed)
        elif state == "ok":
            updated, changed = resolve_key(updated, key, remove=True)
            resolved_count += int(changed)
    validate_store(updated)
    return updated, broken_count, resolved_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", help="JSON map of URL to HTTP status for tests.")
    args = parser.parse_args()
    site = json.loads(SITE_FILE.read_text(encoding="utf-8"))
    people = json.loads(PEOPLE_FILE.read_text(encoding="utf-8")) if PEOPLE_FILE.exists() else {"people": []}
    store = json.loads(STORE_FILE.read_text(encoding="utf-8")) if STORE_FILE.exists() else {}
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else None
    updated, broken_count, resolved_count = run(site, people, store, fixture)
    before = normalized_store(store)
    if updated != before or not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Link check complete; {broken_count} new/updated, {resolved_count} resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
