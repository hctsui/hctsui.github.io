"""Normalize publication metadata and derive consistent display state."""
from __future__ import annotations

import re
from typing import Any

from markup_config import rich_html


PUBLICATION_STATES = {
    "preprint",
    "submitted",
    "under_review",
    "forthcoming",
    "published",
}

JOURNAL_FIELDS = (
    "journaltitle",
    "shortjournal",
    "date",
    "volume",
    "number",
    "pages",
    "eid",
    "publisher",
    "doi",
    "url",
)


def pair_text(value: Any, lang: str) -> str:
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or value.get("zh") or "").strip()
    return str(value or "").strip()


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^doi:\s*", "", text, flags=re.I)
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.I)
    return text.strip().strip("/")


def doi_url(value: Any) -> str:
    doi = normalize_doi(value)
    return f"https://doi.org/{doi}" if doi else ""


def publication_state(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("publication_state") or "").strip().lower()
    aliases = {"accepted": "forthcoming", "to_appear": "forthcoming", "in_press": "forthcoming"}
    explicit = aliases.get(explicit, explicit)
    if explicit in PUBLICATION_STATES:
        return explicit

    venue = " ".join(
        pair_text(entry.get("venue"), lang).casefold() for lang in ("en", "zh")
    )
    if any(token in venue for token in ("to appear", "forthcoming", "accepted", "即將刊登", "已接受")):
        return "forthcoming"
    if "under review" in venue or "審查中" in venue:
        return "under_review"
    if "submitted" in venue or "已投稿" in venue:
        return "submitted"
    if str(entry.get("group_id") or "") == "journal-articles" or entry.get("doi_url") or entry.get("journal_url"):
        return "published"
    return "preprint"


def normalized_journal(entry: dict[str, Any]) -> dict[str, str]:
    raw = entry.get("journal") if isinstance(entry.get("journal"), dict) else {}
    result = {field: str(raw.get(field) or "").strip() for field in JOURNAL_FIELDS}
    result["doi"] = normalize_doi(result["doi"] or entry.get("doi_url"))
    result["url"] = result["url"] or str(entry.get("journal_url") or "").strip()
    if not result["journaltitle"]:
        legacy = pair_text(entry.get("venue"), "en")
        legacy = re.sub(r"\[/?b\]|</?(?:strong|b)>", "", legacy, flags=re.I)
        legacy = re.sub(r"\s*[,;]?\s*arxiv:\s*\S+\s*$", "", legacy, flags=re.I).strip()
        match = re.match(r"^(?:to appear in|accepted(?: for publication)? in)\s+(.+?)[.]?$", legacy, flags=re.I)
        if match:
            label = match.group(1).strip()
            short = re.search(r"\s+\(([^()]+)\)$", label)
            if short:
                result["shortjournal"] = result["shortjournal"] or short.group(1).strip()
                label = label[:short.start()].strip()
            result["journaltitle"] = label
    return result


def journal_label(entry: dict[str, Any]) -> str:
    journal = normalized_journal(entry)
    title = journal["journaltitle"]
    short = journal["shortjournal"]
    if not title:
        return short
    if short and short.casefold() not in title.casefold():
        return f"{title} ({short})"
    return title


def has_formal_journal_metadata(entry: dict[str, Any]) -> bool:
    journal = normalized_journal(entry)
    state = publication_state(entry)
    if state in {"forthcoming", "published"}:
        return True
    # A target journal name alone does not imply acceptance.
    return any(journal[field] for field in ("date", "volume", "number", "pages", "eid", "doi"))


def automatic_group_id(entry: dict[str, Any]) -> str:
    return "journal-articles" if has_formal_journal_metadata(entry) else "preprints"


def _journal_year(entry: dict[str, Any], journal: dict[str, str]) -> str:
    match = re.match(r"^(\d{4})", journal["date"])
    if match:
        return match.group(1)
    return str(entry.get("year") or str(entry.get("date") or "")[:4] or "").strip()


def _published_status(entry: dict[str, Any], lang: str, journal: dict[str, str]) -> str:
    label = journal_label(entry)
    bold_label = f"[b]{label}[/b]" if label else ""
    year = _journal_year(entry, journal)
    volume = journal["volume"]
    number = journal["number"]
    locator = journal["pages"] or journal["eid"]

    text = bold_label
    if volume:
        text += f" {volume}"
    if year:
        text += f" ({year})"
    if number:
        text += ("，第 " if lang == "zh" else ", no. ") + number
    if locator:
        text += ("，" if lang == "zh" else ", ") + locator
    return text or ("已正式出版" if lang == "zh" else "Published")


def publication_status_text(entry: dict[str, Any], lang: str) -> str:
    state = publication_state(entry)
    journal = normalized_journal(entry)
    label = journal_label(entry)
    note = pair_text(entry.get("publication_note"), lang)

    if state == "forthcoming":
        if label:
            base = f"即將刊登於[b]《{label}》[/b]" if lang == "zh" else f"To appear in [b]{label}[/b]"
        else:
            base = "即將刊登" if lang == "zh" else "To appear"
    elif state == "published":
        base = _published_status(entry, lang, journal)
    elif state == "submitted":
        base = "已投稿" if lang == "zh" else "Submitted"
    elif state == "under_review":
        base = "審查中" if lang == "zh" else "Under review"
    else:
        base = ""

    if note:
        base = f"{base} — {note}" if base else note

    arxiv = str(entry.get("arxiv") or "").strip()
    show_arxiv = bool(entry.get("show_arxiv_in_status")) and bool(arxiv)
    if show_arxiv:
        arxiv_text = f"arXiv：{arxiv}" if lang == "zh" else f"arXiv: {arxiv}"
        base = f"{base}；{arxiv_text}" if base and lang == "zh" else f"{base}; {arxiv_text}" if base else arxiv_text

    if not base:
        return ""
    if lang == "zh":
        return base.rstrip("。.;； ") + "。"
    return base.rstrip("。.;； ") + "."


def normalize_publication(entry: dict[str, Any]) -> dict[str, Any]:
    """Mutate and return one publication using the canonical metadata model."""
    legacy_venue = entry.get("venue") if isinstance(entry.get("venue"), dict) else {}
    entry["publication_state"] = publication_state(entry)
    entry["journal"] = normalized_journal(entry)

    if "show_arxiv_in_status" not in entry:
        legacy = " ".join(pair_text(legacy_venue, lang).casefold() for lang in ("en", "zh"))
        entry["show_arxiv_in_status"] = bool(entry.get("arxiv")) and (
            "arxiv" in legacy or entry["publication_state"] == "preprint"
        )
    else:
        entry["show_arxiv_in_status"] = bool(entry["show_arxiv_in_status"])

    mode = str(entry.get("classification_mode") or "").strip().lower()
    if mode not in {"auto", "manual"}:
        mode = "auto" if str(entry.get("group_id") or "preprints") in {"preprints", "journal-articles"} else "manual"
    entry["classification_mode"] = mode
    if mode == "auto":
        entry["group_id"] = automatic_group_id(entry)
        entry["category_id"] = f"publication-{entry['group_id']}"

    arxiv = str(entry.get("arxiv") or "").strip()
    if arxiv and not entry.get("arxiv_url"):
        entry["arxiv_url"] = f"https://arxiv.org/abs/{arxiv}"
    entry["doi_url"] = doi_url(entry["journal"]["doi"])
    entry["journal_url"] = entry["journal"]["url"]

    canonical = {"arxiv", "pdf", "doi", "journal", "code"}
    links = [
        link for link in entry.get("links", [])
        if isinstance(link, dict)
        and str((link.get("label") or {}).get("en") or "").strip().casefold() not in canonical
    ]
    for label, url in (
        ("arXiv", entry.get("arxiv_url")),
        ("PDF", entry.get("pdf_url")),
        ("DOI", entry.get("doi_url")),
        ("Journal", entry.get("journal_url")),
        ("Code", entry.get("code_url")),
    ):
        if url:
            links.append({"label": {"en": label, "zh": label}, "url": str(url).strip()})
    entry["links"] = links

    venue = {
        "en": publication_status_text(entry, "en"),
        "zh": publication_status_text(entry, "zh"),
    }
    entry["venue"] = venue
    entry["venue_html"] = {lang: rich_html(value) for lang, value in venue.items()}
    return entry
