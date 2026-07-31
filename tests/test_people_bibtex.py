from __future__ import annotations

import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import publication_bibtex, render_publication_article, rich_html  # noqa: E402
from people_config import link_author_html, normalized_people, validate_people  # noqa: E402
from process_batch_request import apply_special, apply_undo, empty_history  # noqa: E402


class PeopleDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = normalized_people(
            {
                "schema_version": 1,
                "people": [
                    {
                        "id": "ting-wei-chang",
                        "name": {"en": "Ting-Wei Chang", "zh": "張庭瑋"},
                        "aliases": ["Chang, Ting-Wei"],
                        "url": "https://example.edu/chang",
                    },
                    {
                        "id": "song-yun-chen",
                        "name": {"en": "Song-Yun Chen", "zh": "陳松筠"},
                        "aliases": [],
                        "url": "https://example.edu/chen",
                    },
                ],
            }
        )

    def test_links_exact_names_but_not_own_strong_name(self) -> None:
        html = "Ting-Wei Chang, Song-Yun Chen, and <strong>Hung-Chun Tsui</strong>"
        linked = link_author_html(html, self.people, "en")
        self.assertIn('href="https://example.edu/chang"', linked)
        self.assertIn('href="https://example.edu/chen"', linked)
        self.assertIn("<strong>Hung-Chun Tsui</strong>", linked)
        self.assertNotIn("<a", linked.split("<strong>", 1)[1])

    def test_similar_names_are_not_partial_matches(self) -> None:
        linked = link_author_html("Ting-Wei Chang Jr.", self.people, "en")
        self.assertIn("Ting-Wei Chang Jr.", linked)
        # The canonical name may be linked inside a suffix-bearing name only if the
        # boundary is a real separator. A hyphenated continuation must not match.
        not_linked = link_author_html("Ting-Wei Chang-Smith", self.people, "en")
        self.assertNotIn("author-link", not_linked)

    def test_duplicate_name_or_unsafe_url_is_rejected(self) -> None:
        bad = copy.deepcopy(self.people)
        bad["people"][1]["aliases"] = ["Ting-Wei Chang"]
        with self.assertRaises(ValueError):
            validate_people(bad)
        bad = copy.deepcopy(self.people)
        bad["people"][0]["url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            validate_people(bad)

    def test_people_batch_operation_and_undo(self) -> None:
        data = {"settings": {}, "activities": [], "honors": [], "publications": [], "teaching": [], "profile_items": []}
        translations = {"schema_version": 1, "pairs": []}
        people = {"schema_version": 1, "people": []}
        history = empty_history()
        operation = {"op": "people", "before": copy.deepcopy(people), "after": self.people}
        action, entry_id = apply_special(
            data,
            translations,
            history,
            operation,
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest-1",
            people=people,
        )
        self.assertEqual((action, entry_id), ("people", "people"))
        self.assertEqual(len(people["people"]), 2)
        undo_action, undo_id = apply_undo(
            data,
            translations,
            history,
            {"op": "undo", "history_id": "issue-1-op-1"},
            "issue-2-op-1",
            2,
            datetime.now(timezone.utc),
            "digest-2",
            people=people,
        )
        self.assertEqual((undo_action, undo_id), ("undo", "people"))
        self.assertEqual(people["people"], [])


class BibtexTests(unittest.TestCase):
    def publication(self) -> dict:
        return {
            "id": "publication-example",
            "type": "publication",
            "date": "2026-03-10",
            "year": 2026,
            "title": {"en": "Algebra Structures of Multiple Eisenstein Series", "zh": ""},
            "authors": {"en": "Ting-Wei Chang and Hung-Chun Tsui", "zh": ""},
            "venue": {"en": "arXiv:2603.10376", "zh": ""},
            "arxiv": "2603.10376",
            "arxiv_url": "https://arxiv.org/abs/2603.10376",
            "links": [{"label": {"en": "arXiv", "zh": "arXiv"}, "url": "https://arxiv.org/abs/2603.10376"}],
        }

    def test_auto_generated_bibtex_contains_core_fields(self) -> None:
        text = publication_bibtex(self.publication())
        self.assertIn("@misc{", text)
        self.assertIn("author = {Ting-Wei Chang and Hung-Chun Tsui}", text)
        self.assertIn("eprint = {2603.10376}", text)
        self.assertIn("archivePrefix = {arXiv}", text)

    def test_manual_bibtex_wins(self) -> None:
        item = self.publication()
        item["bibtex"] = "@article{custom, title={Exact publisher record}}"
        self.assertEqual(publication_bibtex(item), item["bibtex"])

    def test_publication_html_has_expand_and_copy_controls(self) -> None:
        rendered = render_publication_article(self.publication(), "en")
        self.assertIn("data-bibtex-toggle", rendered)
        self.assertIn("data-copy-bibtex", rendered)
        self.assertIn("Copy BibTeX", rendered)


class StaticMathTests(unittest.TestCase):
    def test_common_number_theory_tex_is_rendered_without_external_dependency(self) -> None:
        rendered = rich_html(r"$\mathfrak{p}$-adic over $\mathbb{F}_q((t))$")
        self.assertIn("𝔭", rendered)
        self.assertIn("𝔽", rendered)
        self.assertIn("<sub>q</sub>", rendered)
        self.assertNotIn("\\mathfrak", rendered)


if __name__ == "__main__":
    unittest.main()
