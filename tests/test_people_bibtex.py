from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import assign_citation_keys, publication_bibitem, publication_bibtex, render_publication_article, replace_main, rich_html  # noqa: E402
from people_config import link_author_html, link_people_html, normalized_people, validate_people  # noqa: E402
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

    def test_general_page_text_links_people_outside_publications(self) -> None:
        source = '<p>Advisor: Ting-Wei Chang</p><p>Hosted by Song-Yun Chen.</p>'
        linked = link_people_html(source, self.people, "en")
        self.assertEqual(linked.count('class="person-link"'), 2)
        self.assertIn('Advisor: <a class="person-link"', linked)

    def test_general_linking_does_not_touch_existing_links_or_similar_names(self) -> None:
        source = '<p><a href="/existing">Ting-Wei Chang</a> and Ting-Wei Chang-Smith</p>'
        linked = link_people_html(source, self.people, "en")
        self.assertEqual(linked.count('<a '), 1)
        self.assertNotIn('person-link', linked)

    def test_longest_person_name_wins_without_nested_links(self) -> None:
        people = normalized_people({"schema_version": 1, "people": [
            {"id": "chang", "name": {"en": "Chang", "zh": ""}, "aliases": [], "url": "https://example.edu/c"},
            {"id": "ting-wei-chang", "name": {"en": "Ting-Wei Chang", "zh": ""}, "aliases": [], "url": "https://example.edu/t"},
        ]})
        linked = link_people_html('<p>Ting-Wei Chang</p>', people, 'en')
        self.assertEqual(linked.count('person-link'), 1)
        self.assertIn('https://example.edu/t', linked)

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

    def test_committed_people_directory_is_valid(self) -> None:
        people = json.loads((ROOT / "content" / "people.json").read_text(encoding="utf-8"))
        validate_people(people)

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
        item = self.publication()
        item["primary_category"] = "math.NT"
        text = publication_bibtex(item)
        self.assertIn("@misc{CT26,", text)
        self.assertIn("title = {Algebra Structures of Multiple Eisenstein Series}", text)
        self.assertIn("author = {Ting-Wei Chang and Hung-Chun Tsui}", text)
        self.assertIn("eprint = {2603.10376}", text)
        self.assertIn("archivePrefix = {arXiv}", text)
        self.assertIn("primaryClass = {math.NT}", text)

    def test_duplicate_author_year_keys_receive_letter_suffixes(self) -> None:
        first = self.publication()
        second = self.publication() | {"id": "publication-example-2", "date": "2026-04-01", "title": {"en": "Second paper", "zh": ""}}
        data = {"publications": [second, first]}
        assign_citation_keys(data)
        self.assertEqual(first["_citation_key"], "CT26a")
        self.assertEqual(second["_citation_key"], "CT26b")
        self.assertIn("@misc{CT26a,", publication_bibtex(first))
        self.assertIn(r"\bibitem{CT26b}", publication_bibitem(second))

    def test_manual_bibtex_wins(self) -> None:
        item = self.publication()
        item["bibtex"] = "@article{custom, title={Exact publisher record}}"
        self.assertEqual(publication_bibtex(item), item["bibtex"])

    def test_auto_generated_bibitem_contains_core_fields(self) -> None:
        text = publication_bibitem(self.publication())
        self.assertIn(r"\bibitem{", text)
        self.assertIn("Ting-Wei Chang and Hung-Chun Tsui", text)
        self.assertIn(r"\emph{Algebra Structures of Multiple Eisenstein Series}", text)
        self.assertIn("arXiv:2603.10376", text)


    def test_bibitem_preserves_inline_italic_symbols_as_math(self) -> None:
        item = self.publication()
        item["title"] = {"en": "On u -Multiple Zeta Values", "zh": ""}
        item["title_html"] = {"en": "On <em>u</em>-Multiple Zeta Values", "zh": ""}
        text = publication_bibitem(item)
        self.assertIn(r"\emph{On $u$-Multiple Zeta Values}", text)

    def test_manual_bibitem_wins(self) -> None:
        item = self.publication()
        item["bibitem"] = r"\bibitem{custom} Exact legacy citation."
        self.assertEqual(publication_bibitem(item), item["bibitem"])


    def test_main_replacement_accepts_latex_backslashes(self) -> None:
        page = '<html><body><main id="main">old</main></body></html>'
        replaced = replace_main(page, r'<pre>\bibitem{x} \emph{Title}</pre>')
        self.assertIn(r'\bibitem{x} \emph{Title}', replaced)

    def test_publication_html_has_matching_action_buttons_and_working_citation_controls(self) -> None:
        rendered = render_publication_article(self.publication(), "en")
        self.assertIn('<a class="publication-action"', rendered)
        self.assertIn('class="publication-action pub-citation-toggle"', rendered)
        self.assertIn("data-bibtex-toggle", rendered)
        self.assertIn("data-citation-toggle", rendered)
        self.assertIn("data-citation-close", rendered)
        self.assertIn("data-copy-bibtex", rendered)
        self.assertIn("data-copy-citation", rendered)
        self.assertIn('data-citation-format="bibtex"', rendered)
        self.assertIn('data-citation-format="bibitem"', rendered)
        self.assertIn('class="citation-panel"', rendered)
        self.assertIn("Copy biblatex", rendered)
        self.assertIn(r"Copy \bibitem", rendered)
        self.assertIn(">Cite</button>", rendered)
        self.assertIn(r"LaTeX \bibitem", rendered)
        self.assertNotIn("\b", rendered)


class StaticMathTests(unittest.TestCase):
    def test_common_number_theory_tex_is_rendered_without_external_dependency(self) -> None:
        rendered = rich_html(r"$\mathfrak{p}$-adic over $\mathbb{F}_q((t))$")
        self.assertIn("𝔭", rendered)
        self.assertIn("𝔽", rendered)
        self.assertIn("<sub>q</sub>", rendered)
        self.assertNotIn("\\mathfrak", rendered)


if __name__ == "__main__":
    unittest.main()
