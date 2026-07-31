#!/usr/bin/env python3
"""Person-link database normalization, validation, and safe HTML linking."""
from __future__ import annotations

import copy
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_FILE = ROOT / "content" / "people.json"
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def empty_people() -> dict[str, Any]:
    return {"schema_version": 1, "people": []}


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def slug(value: Any) -> str:
    text = normalized_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:64] or "person"


def normalize_aliases(value: Any, canonical: set[str]) -> list[str]:
    if isinstance(value, str):
        source = re.split(r"[\n,，]+", value)
    elif isinstance(value, list):
        source = value
    else:
        source = []
    result: list[str] = []
    seen: set[str] = set()
    for item in source:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = normalized_text(text)
        if not text or not key or key in canonical or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def normalized_people(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    rows = source.get("people") if isinstance(source.get("people"), list) else []
    result: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for index, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            continue
        name_raw = raw.get("name") if isinstance(raw.get("name"), dict) else {}
        name = {
            "en": re.sub(r"\s+", " ", str(name_raw.get("en") or "").strip()),
            "zh": re.sub(r"\s+", " ", str(name_raw.get("zh") or "").strip()),
        }
        canonical = {normalized_text(name["en"]), normalized_text(name["zh"])} - {""}
        aliases = normalize_aliases(raw.get("aliases"), canonical)
        base_id = str(raw.get("id") or "").strip().lower() or slug(name["en"] or name["zh"] or f"person-{index}")
        base_id = re.sub(r"[^a-z0-9]+", "-", base_id).strip("-") or f"person-{index}"
        person_id = base_id
        suffix = 2
        while person_id in used_ids:
            person_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(person_id)
        result.append(
            {
                "id": person_id,
                "name": name,
                "aliases": aliases,
                "url": str(raw.get("url") or "").strip(),
            }
        )
    return {"schema_version": 1, "people": result}


def validate_people(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("People directory must be an object.")
    if value.get("schema_version") != 1:
        raise ValueError("People directory schema_version must be 1.")
    rows = value.get("people")
    if not isinstance(rows, list):
        raise ValueError("People directory people must be a list.")
    if len(rows) > 1000:
        raise ValueError("People directory is too large.")
    ids: set[str] = set()
    lookup: dict[str, str] = {}
    for index, person in enumerate(rows, start=1):
        if not isinstance(person, dict):
            raise ValueError(f"Person {index} must be an object.")
        person_id = str(person.get("id") or "").strip()
        if not ID_RE.fullmatch(person_id):
            raise ValueError(f"Person {index} has an invalid id: {person_id!r}.")
        if person_id in ids:
            raise ValueError(f"Duplicate person id: {person_id}.")
        ids.add(person_id)
        name = person.get("name")
        if not isinstance(name, dict):
            raise ValueError(f"Person {person_id} is missing name data.")
        names = [str(name.get("en") or "").strip(), str(name.get("zh") or "").strip()]
        if not any(names):
            raise ValueError(f"Person {person_id} needs an English or Chinese name.")
        aliases = person.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError(f"Person {person_id} aliases must be a list.")
        url = str(person.get("url") or "").strip()
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Person {person_id} URL must be a complete http or https URL.")
            if any(ch.isspace() for ch in url):
                raise ValueError(f"Person {person_id} URL cannot contain whitespace.")
        for candidate in [*names, *aliases]:
            key = normalized_text(candidate)
            if not key:
                continue
            owner = lookup.get(key)
            if owner and owner != person_id:
                raise ValueError(f"Name or alias {candidate!r} is assigned to both {owner} and {person_id}.")
            lookup[key] = person_id


def load_people(path: Path = PEOPLE_FILE) -> dict[str, Any]:
    if not path.exists():
        return empty_people()
    import json

    data = normalized_people(json.loads(path.read_text(encoding="utf-8")))
    validate_people(data)
    return data


def person_link_names(value: Any, lang: str) -> list[tuple[str, str]]:
    data = normalized_people(value)
    result: list[tuple[str, str]] = []
    for person in data["people"]:
        url = str(person.get("url") or "").strip()
        if not url:
            continue
        name = person.get("name") or {}
        candidates = [str(name.get(lang) or "").strip()]
        candidates.extend(str(alias or "").strip() for alias in person.get("aliases", []))
        # The opposite-language canonical name is also safe to recognize. This
        # covers old homepage records whose Chinese copy still contains English names.
        candidates.append(str(name.get("zh" if lang == "en" else "en") or "").strip())
        seen: set[str] = set()
        for candidate in candidates:
            key = normalized_text(candidate)
            if not candidate or not key or key in seen:
                continue
            seen.add(key)
            result.append((candidate, url))
    result.sort(key=lambda item: len(item[0]), reverse=True)
    return result


def _name_pattern(name: str) -> re.Pattern[str]:
    escaped = re.escape(name)
    # Author names must occupy a complete author-list token.  A mere prefix
    # match such as “Ting-Wei Chang Jr.” is intentionally not linked because
    # it may refer to a different person with a similar name.
    delimiter = r"(?=\s*(?:,|，|、|;|；|\band\b|&|$))"
    if re.search(r"[A-Za-z0-9]", name):
        return re.compile(rf"(?<![\w-]){escaped}{delimiter}", re.IGNORECASE)
    return re.compile(rf"{escaped}{delimiter}")


class _AuthorLinker(HTMLParser):
    def __init__(self, names: list[tuple[str, str]]) -> None:
        super().__init__(convert_charrefs=False)
        self.names = [(name, url, _name_pattern(name)) for name, url in names]
        self.parts: list[str] = []
        self.blocked_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        self.parts.append(raw)
        if tag.lower() in {"a", "strong"}:
            self.blocked_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if tag.lower() in {"a", "strong"} and self.blocked_depth:
            self.blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.blocked_depth or not self.names:
            self.parts.append(data)
            return
        text = data
        for name, url, pattern in self.names:
            safe_url = html.escape(url, quote=True)
            text = pattern.sub(
                lambda match: (
                    f'<a class="author-link" href="{safe_url}" rel="noopener" '
                    f'target="_blank">{match.group(0)}</a>'
                ),
                text,
            )
        self.parts.append(text)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def get_html(self) -> str:
        return "".join(self.parts)


def link_author_html(fragment: str, people: Any, lang: str) -> str:
    names = person_link_names(people, lang)
    if not fragment or not names:
        return fragment
    parser = _AuthorLinker(names)
    parser.feed(fragment)
    parser.close()
    return parser.get_html()



def _general_name_pattern(name: str) -> re.Pattern[str]:
    escaped = re.escape(name)
    if re.search(r"[A-Za-z0-9]", name):
        return re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)
    return re.compile(escaped)


def _link_visible_text(data: str, names: list[tuple[str, str]], css_class: str) -> str:
    """Insert links into the original text only, choosing longest non-overlapping names."""
    candidates: list[tuple[int, int, str]] = []
    for name, url in names:
        pattern = _general_name_pattern(name)
        candidates.extend((match.start(), match.end(), url) for match in pattern.finditer(data))
    if not candidates:
        return data
    candidates.sort(key=lambda row: (row[0], -(row[1] - row[0])))
    selected: list[tuple[int, int, str]] = []
    cursor = -1
    for start, end, url in candidates:
        if start < cursor:
            continue
        selected.append((start, end, url))
        cursor = end
    parts: list[str] = []
    cursor = 0
    for start, end, url in selected:
        parts.append(data[cursor:start])
        label = data[start:end]
        parts.append(
            f'<a class="{css_class}" href="{html.escape(url, quote=True)}" '
            f'rel="noopener" target="_blank">{label}</a>'
        )
        cursor = end
    parts.append(data[cursor:])
    return "".join(parts)


class _DocumentPersonLinker(HTMLParser):
    """Link visible person names while leaving existing semantic markup untouched."""

    BLOCKED_TAGS = {"a", "strong", "script", "style", "code", "pre", "textarea", "title", "head", "svg"}

    def __init__(self, names: list[tuple[str, str]]) -> None:
        super().__init__(convert_charrefs=False)
        self.names = names
        self.parts: list[str] = []
        self.blocked_depth = 0

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")
        if tag.lower() in self.BLOCKED_TAGS:
            self.blocked_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if tag.lower() in self.BLOCKED_TAGS and self.blocked_depth:
            self.blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        self.parts.append(data if self.blocked_depth else _link_visible_text(data, self.names, "person-link"))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def get_html(self) -> str:
        return "".join(self.parts)


def link_people_html(fragment: str, people: Any, lang: str) -> str:
    names = person_link_names(people, lang)
    if not fragment or not names:
        return fragment
    parser = _DocumentPersonLinker(names)
    parser.feed(fragment)
    parser.close()
    return parser.get_html()


def people_snapshot(value: Any) -> dict[str, Any]:
    return copy.deepcopy(normalized_people(value))
