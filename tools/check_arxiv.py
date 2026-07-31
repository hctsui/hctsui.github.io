#!/usr/bin/env python3
"""Query the official arXiv API and update pending Admin suggestions."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arxiv_suggestions import (
    exact_author_match,
    normalize_arxiv_id,
    normalized_store,
    publication_arxiv_ids,
    validate_store,
)

ROOT = Path(__file__).resolve().parents[1]
SITE_FILE = ROOT / "content" / "site.json"
STORE_FILE = ROOT / "content" / "arxiv-suggestions.json"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
API_URL = "https://export.arxiv.org/api/query"


def text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return " ".join((child.text or "").split()) if child is not None else ""


def parse_feed(payload: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    results: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = text(entry, f"{ATOM}id")
        arxiv_id = normalize_arxiv_id(raw_id)
        if not arxiv_id or raw_id.endswith("/api/errors"):
            continue
        authors = [text(author, f"{ATOM}name") for author in entry.findall(f"{ATOM}author")]
        links = entry.findall(f"{ATOM}link")
        alternate = next((link.get("href", "") for link in links if link.get("rel") == "alternate"), "")
        pdf = next((link.get("href", "") for link in links if link.get("title") == "pdf"), "")
        categories = [node.get("term", "") for node in entry.findall(f"{ATOM}category") if node.get("term")]
        primary = entry.find(f"{ARXIV}primary_category")
        results.append({
            "arxiv_id": arxiv_id,
            "title": text(entry, f"{ATOM}title"),
            "authors": authors,
            "summary": text(entry, f"{ATOM}summary"),
            "published": text(entry, f"{ATOM}published"),
            "updated": text(entry, f"{ATOM}updated"),
            "primary_category": primary.get("term", "") if primary is not None else "",
            "categories": categories,
            "arxiv_url": alternate or f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf or f"https://arxiv.org/pdf/{arxiv_id}",
            "doi": text(entry, f"{ARXIV}doi"),
            "journal_ref": text(entry, f"{ARXIV}journal_ref"),
        })
    return results


def fetch_results(store: dict[str, Any], timeout: int = 30) -> list[dict[str, Any]]:
    search = store["search"]
    query = f'au:"{search["author_query"]}"'
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": search["max_results"],
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    request = urllib.request.Request(
        f"{API_URL}?{params}",
        headers={
            "User-Agent": "hctsui.github.io academic-site arXiv suggestion checker (contact: hctsui.math@gmail.com)",
            "Accept": "application/atom+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_feed(response.read())


def update_store(store: dict[str, Any], site: dict[str, Any], fetched: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    current = normalized_store(store)
    existing_ids = publication_arxiv_ids(site)
    ignored = set(current["ignored_ids"])
    accepted_names = current["search"]["author_names"]
    merged = {item["arxiv_id"]: item for item in current["suggestions"] if item["arxiv_id"] not in existing_ids and item["arxiv_id"] not in ignored}
    for item in fetched:
        arxiv_id = normalize_arxiv_id(item.get("arxiv_id"))
        if not arxiv_id or arxiv_id in existing_ids or arxiv_id in ignored:
            continue
        if not exact_author_match(item.get("authors", []), accepted_names):
            continue
        merged[arxiv_id] = item
    suggestions = sorted(merged.values(), key=lambda item: (item.get("published", ""), item["arxiv_id"]), reverse=True)
    before_signature = json.dumps(current["suggestions"], ensure_ascii=False, sort_keys=True)
    after_signature = json.dumps(suggestions, ensure_ascii=False, sort_keys=True)
    changed = before_signature != after_signature
    result = dict(current)
    result["suggestions"] = suggestions
    if changed:
        result["checked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    validate_store(result)
    return result, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed-file", help="Use a local Atom feed instead of making a network request.")
    args = parser.parse_args()
    site = json.loads(SITE_FILE.read_text(encoding="utf-8"))
    raw_store = json.loads(STORE_FILE.read_text(encoding="utf-8")) if STORE_FILE.exists() else {}
    store = normalized_store(raw_store)
    fetched = parse_feed(Path(args.feed_file).read_bytes()) if args.feed_file else fetch_results(store)
    updated, changed = update_store(store, site, fetched)
    if changed or not STORE_FILE.exists():
        STORE_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {STORE_FILE.relative_to(ROOT)} with {len(updated['suggestions'])} pending suggestion(s).")
    else:
        print("No new arXiv suggestions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
