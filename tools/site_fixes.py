#!/usr/bin/env python3
"""Minimal publication and CV presentation fixes for the CMS build pipeline.

These are output-only changes. The underlying CMS data and publication dates
remain intact, and the original renderers remain the source of truth.
"""
from __future__ import annotations

import re
from typing import Any


def install_publication_labels() -> None:
    """Use ArXiv as the public link caption without changing stored records."""
    import process_request as core

    original = core.normalize_publication
    if getattr(original, "_hctsui_arxiv_label_fixed", False):
        return

    def normalize_publication(entry: dict[str, Any]) -> dict[str, Any]:
        normalized = original(entry)
        for link in normalized.get("links", []):
            labels = link.get("label") if isinstance(link, dict) else None
            if isinstance(labels, dict) and str(labels.get("en") or "").casefold() == "arxiv":
                labels["en"] = "ArXiv"
                labels["zh"] = "ArXiv"
        return normalized

    normalize_publication._hctsui_arxiv_label_fixed = True
    core.normalize_publication = normalize_publication


def patch_build_site(module: Any) -> None:
    """Show only the publication year in automatically generated biblatex."""
    if getattr(module, "_hctsui_publication_biblatex_fixed", False):
        return
    original = module.publication_bibtex

    def publication_bibtex(entry: dict[str, Any]) -> str:
        # Honor a manually entered biblatex record exactly as written.
        if str(entry.get("bibtex") or "").strip():
            return original(entry)
        journal = module.normalized_journal(entry)
        full_date = journal.get("date", "")
        if not full_date:
            return original(entry)
        # Copy instead of mutating CMS metadata: sorting and editing still see YYYY-MM-DD.
        public_entry = dict(entry)
        public_entry["journal"] = dict(entry.get("journal") or {})
        public_entry["journal"]["date"] = full_date[:4]
        return original(public_entry)

    module.publication_bibtex = publication_bibtex
    module._hctsui_publication_biblatex_fixed = True


def patch_build_cv(module: Any) -> None:
    """Restart publication numbering by group and omit duplicate journal year."""
    if getattr(module, "_hctsui_cv_publications_fixed", False):
        return
    original_rows = module.render_category_rows
    original_publication = module.render_publication

    def render_category_rows(data, category, lang, today, publication_start=1):
        if category.get("kind") == "publication":
            publication_start = 1
        return original_rows(data, category, lang, today, publication_start)

    def render_publication(entry, number, lang):
        output = original_publication(entry, number, lang)
        year = str(entry.get("year") or "")
        venue = module.pair(entry, "venue", lang).strip()
        # Only suppress the *second* year appended after an already dated venue.
        if year and (re.search(rf"(?<!\d){re.escape(year)}(?!\d)", venue)
                     or (entry.get("publication_state") == "published"
                         and re.search(r"(?<!\d)\d{4}(?!\d)", venue))):
            ending = f", {year}.\n\\end{{pub}}"
            if output.endswith(ending):
                output = output[:-len(ending)] + ".\n\\end{pub}"
        return output

    module.render_category_rows = render_category_rows
    module.render_publication = render_publication
    module._hctsui_cv_publications_fixed = True
