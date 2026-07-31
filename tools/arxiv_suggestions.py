#!/usr/bin/env python3
"""Shared model helpers for arXiv publication suggestions."""
from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_SEARCH = {
    "author_query": "Hung-Chun Tsui",
    "author_names": ["Hung-Chun Tsui"],
    "max_results": 30,
}


def normalize_arxiv_id(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", text, flags=re.I)
    text = re.sub(r"\.pdf$", "", text, flags=re.I)
    return re.sub(r"v\d+$", "", text, flags=re.I).strip()


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def empty_store() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "search": copy.deepcopy(DEFAULT_SEARCH),
        "ignored_ids": [],
        "checked_at": "",
        "suggestions": [],
    }


def normalized_store(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    search = source.get("search") if isinstance(source.get("search"), dict) else {}
    names: list[str] = []
    for raw in search.get("author_names", DEFAULT_SEARCH["author_names"]):
        name = str(raw or "").strip()
        if name and name not in names:
            names.append(name)
    if not names:
        names = list(DEFAULT_SEARCH["author_names"])
    max_results = search.get("max_results", DEFAULT_SEARCH["max_results"])
    try:
        max_results = max(1, min(100, int(max_results)))
    except (TypeError, ValueError):
        max_results = DEFAULT_SEARCH["max_results"]

    ignored: list[str] = []
    for raw in source.get("ignored_ids", []):
        arxiv_id = normalize_arxiv_id(raw)
        if arxiv_id and arxiv_id not in ignored:
            ignored.append(arxiv_id)

    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source.get("suggestions", []):
        if not isinstance(raw, dict):
            continue
        arxiv_id = normalize_arxiv_id(raw.get("arxiv_id") or raw.get("id"))
        if not arxiv_id or arxiv_id in seen or arxiv_id in ignored:
            continue
        seen.add(arxiv_id)
        authors = [str(x or "").strip() for x in raw.get("authors", []) if str(x or "").strip()]
        categories = [str(x or "").strip() for x in raw.get("categories", []) if str(x or "").strip()]
        suggestions.append({
            "arxiv_id": arxiv_id,
            "title": str(raw.get("title") or "").strip(),
            "authors": authors,
            "summary": str(raw.get("summary") or "").strip(),
            "published": str(raw.get("published") or "").strip(),
            "updated": str(raw.get("updated") or "").strip(),
            "primary_category": str(raw.get("primary_category") or "").strip(),
            "categories": categories,
            "arxiv_url": str(raw.get("arxiv_url") or f"https://arxiv.org/abs/{arxiv_id}").strip(),
            "pdf_url": str(raw.get("pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}").strip(),
            "doi": str(raw.get("doi") or "").strip(),
            "journal_ref": str(raw.get("journal_ref") or "").strip(),
        })
    suggestions.sort(key=lambda item: (item.get("published", ""), item["arxiv_id"]), reverse=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "search": {
            "author_query": str(search.get("author_query") or DEFAULT_SEARCH["author_query"]).strip(),
            "author_names": names,
            "max_results": max_results,
        },
        "ignored_ids": ignored,
        "checked_at": str(source.get("checked_at") or "").strip(),
        "suggestions": suggestions,
    }


def validate_store(value: Any) -> None:
    store = normalized_store(value)
    if not store["search"]["author_query"]:
        raise ValueError("arXiv author query cannot be blank.")
    if not store["search"]["author_names"]:
        raise ValueError("At least one exact arXiv author name is required.")
    for item in store["suggestions"]:
        if not item["title"] or not item["authors"]:
            raise ValueError(f"arXiv suggestion {item['arxiv_id']} is missing title or authors.")


def publication_arxiv_ids(site: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for item in site.get("publications", []):
        arxiv_id = normalize_arxiv_id(item.get("arxiv"))
        if arxiv_id:
            result.add(arxiv_id)
        for link in item.get("links", []):
            if isinstance(link, dict):
                candidate = normalize_arxiv_id(link.get("url"))
                if candidate and re.match(r"^(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})$", candidate, flags=re.I):
                    result.add(candidate)
    return result


def exact_author_match(authors: list[str], accepted_names: list[str]) -> bool:
    accepted = {normalize_name(name) for name in accepted_names if normalize_name(name)}
    return any(normalize_name(author) in accepted for author in authors)
