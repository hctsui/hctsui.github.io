#!/usr/bin/env python3
"""Find likely journal publications for current preprints via Crossref."""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from notification_store import normalized_store, upsert, validate_store

ROOT = Path(__file__).resolve().parents[1]
SITE_FILE = ROOT / "content" / "site.json"
STORE_FILE = ROOT / "content" / "notifications.json"
API = "https://api.crossref.org/works"


def clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def title_of(entry: dict[str, Any]) -> str:
    title = entry.get("title")
    return str(title.get("en") if isinstance(title, dict) else title or "").strip()


def authors_of(entry: dict[str, Any]) -> str:
    authors = entry.get("authors")
    return str(authors.get("en") if isinstance(authors, dict) else authors or "").strip()


def is_preprint(entry: dict[str, Any]) -> bool:
    if str(entry.get("doi_url") or "").strip():
        return False
    return str(entry.get("group_id") or "") == "preprints" or "arxiv" in str((entry.get("venue") or {}).get("en") or "").casefold()


def crossref_request(entry: dict[str, Any], rows: int = 5, timeout: int = 30) -> list[dict[str, Any]]:
    params = {
        "query.bibliographic": title_of(entry),
        "query.author": "Tsui",
        "rows": rows,
        "select": "DOI,title,author,container-title,published,published-print,published-online,volume,issue,page,URL,type,score",
        "mailto": "hctsui.math@gmail.com",
    }
    request = urllib.request.Request(
        f"{API}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "hctsui.github.io academic-site publication-status checker (mailto:hctsui.math@gmail.com)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return list(payload.get("message", {}).get("items", []))


def load_fixture(path: str) -> dict[str, list[dict[str, Any]]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def first_text(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0] if value else "").strip()
    return str(value or "").strip()


def crossref_year(item: dict[str, Any]) -> int:
    for field in ("published-print", "published-online", "published"):
        parts = item.get(field, {}).get("date-parts", []) if isinstance(item.get(field), dict) else []
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError, IndexError):
                pass
    return 0


def author_names(item: dict[str, Any]) -> list[str]:
    result = []
    for author in item.get("author", []) if isinstance(item.get("author"), list) else []:
        if not isinstance(author, dict):
            continue
        name = " ".join(x for x in (str(author.get("given") or "").strip(), str(author.get("family") or "").strip()) if x)
        if name:
            result.append(name)
    return result


def match_candidate(entry: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    expected_title = clean_text(title_of(entry))
    expected_year = int(entry.get("year") or 0)
    best: dict[str, Any] | None = None
    best_score = 0.0
    for candidate in candidates:
        doi = str(candidate.get("DOI") or "").strip().lower()
        title = first_text(candidate.get("title"))
        if not doi or not title:
            continue
        names = [clean_text(name) for name in author_names(candidate)]
        if not any("tsui" in name.split() for name in names):
            continue
        title_score = SequenceMatcher(None, expected_title, clean_text(title)).ratio()
        year = crossref_year(candidate)
        year_score = 1.0 if not expected_year or not year or year >= expected_year else 0.0
        score = title_score * 0.94 + year_score * 0.06
        if score > best_score:
            best, best_score = candidate, score
    return best, best_score


def candidate_payload(entry: dict[str, Any], item: dict[str, Any], score: float) -> dict[str, Any]:
    doi = str(item.get("DOI") or "").strip().lower()
    container = first_text(item.get("container-title"))
    year = crossref_year(item)
    volume = str(item.get("volume") or "").strip()
    issue = str(item.get("issue") or "").strip()
    pages = str(item.get("page") or "").strip()
    details = ", ".join(x for x in (container, f"vol. {volume}" if volume else "", f"no. {issue}" if issue else "", pages, str(year) if year else "") if x)
    return {
        "key": f"publication-status:{entry.get('id')}:{doi}",
        "type": "publication_status",
        "title": f"可能已正式出版：《{title_of(entry)}》",
        "message": f"Crossref 找到 DOI {doi}" + (f"；{details}" if details else "") + f"。題名匹配度 {score:.0%}，請人工確認後再更新。",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_url": f"https://doi.org/{doi}",
        "payload": {
            "entry_id": str(entry.get("id") or ""),
            "doi": doi,
            "doi_url": f"https://doi.org/{doi}",
            "journal_url": str(item.get("URL") or f"https://doi.org/{doi}"),
            "journal": container,
            "year": year,
            "volume": volume,
            "issue": issue,
            "pages": pages,
            "crossref_title": first_text(item.get("title")),
            "crossref_authors": author_names(item),
            "match_score": round(score, 4),
        },
        "actions": [{"id": "publish", "label": "轉為 Published"}],
    }


def run(site: dict[str, Any], store: dict[str, Any], fixture: dict[str, list[dict[str, Any]]] | None = None, threshold: float = 0.91) -> tuple[dict[str, Any], int]:
    updated = normalized_store(store)
    added = 0
    for entry in site.get("publications", []):
        if not isinstance(entry, dict) or not is_preprint(entry) or not title_of(entry):
            continue
        candidates = fixture.get(str(entry.get("id")), []) if fixture is not None else crossref_request(entry)
        match, score = match_candidate(entry, candidates)
        if not match or score < threshold:
            continue
        updated, changed = upsert(updated, candidate_payload(entry, match, score))
        added += int(changed)
    validate_store(updated)
    return updated, added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", help="JSON mapping publication id to Crossref item arrays.")
    parser.add_argument("--threshold", type=float, default=float(os.getenv("CROSSREF_MATCH_THRESHOLD", "0.91")))
    args = parser.parse_args()
    site = json.loads(SITE_FILE.read_text(encoding="utf-8"))
    store = json.loads(STORE_FILE.read_text(encoding="utf-8")) if STORE_FILE.exists() else {}
    fixture = load_fixture(args.fixture) if args.fixture else None
    updated, count = run(site, store, fixture, args.threshold)
    before = normalized_store(store)
    if updated != before or not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Publication status check complete; {count} notification change(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
