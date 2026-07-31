from __future__ import annotations

import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from arxiv_suggestions import empty_store, normalized_store  # noqa: E402
from check_arxiv import parse_feed, update_store  # noqa: E402
from process_batch_request import apply_special, apply_undo, empty_history  # noqa: E402


SAMPLE_FEED = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>https://arxiv.org/abs/2608.01234v1</id>
    <updated>2026-08-03T00:00:00Z</updated>
    <published>2026-08-03T00:00:00Z</published>
    <title> A New Function Field Result </title>
    <summary>  This is a test abstract. </summary>
    <author><name>Hung-Chun Tsui</name></author>
    <author><name>Example Collaborator</name></author>
    <category term="math.NT" />
    <arxiv:primary_category term="math.NT" />
    <link href="https://arxiv.org/abs/2608.01234v1" rel="alternate" type="text/html" />
    <link href="https://arxiv.org/pdf/2608.01234v1" rel="related" title="pdf" type="application/pdf" />
  </entry>
  <entry>
    <id>https://arxiv.org/abs/2608.09999v1</id>
    <updated>2026-08-04T00:00:00Z</updated>
    <published>2026-08-04T00:00:00Z</published>
    <title>Same surname, different person</title>
    <summary>Should be filtered after the API query.</summary>
    <author><name>Hung Tsui</name></author>
    <category term="math.NT" />
    <link href="https://arxiv.org/abs/2608.09999v1" rel="alternate" type="text/html" />
  </entry>
</feed>'''


class ArxivFeedTests(unittest.TestCase):
    def test_feed_parser_extracts_atom_metadata(self) -> None:
        results = parse_feed(SAMPLE_FEED)
        self.assertEqual(results[0]["arxiv_id"], "2608.01234")
        self.assertEqual(results[0]["authors"], ["Hung-Chun Tsui", "Example Collaborator"])
        self.assertEqual(results[0]["primary_category"], "math.NT")
        self.assertIn("test abstract", results[0]["summary"])

    def test_update_requires_exact_configured_author_and_skips_existing(self) -> None:
        store = empty_store()
        site = {"publications": []}
        updated, changed = update_store(store, site, parse_feed(SAMPLE_FEED))
        self.assertTrue(changed)
        self.assertEqual([x["arxiv_id"] for x in updated["suggestions"]], ["2608.01234"])

        site = {"publications": [{"arxiv": "2608.01234"}]}
        updated, changed = update_store(store, site, parse_feed(SAMPLE_FEED))
        self.assertFalse(updated["suggestions"])

    def test_ignored_id_does_not_return(self) -> None:
        store = empty_store()
        store["ignored_ids"] = ["2608.01234"]
        updated, _ = update_store(store, {"publications": []}, parse_feed(SAMPLE_FEED))
        self.assertFalse(updated["suggestions"])


class ArxivBatchTests(unittest.TestCase):
    def test_ignore_operation_and_undo(self) -> None:
        data = {"settings": {}, "activities": [], "honors": [], "publications": [], "teaching": [], "profile_items": []}
        translations = {"schema_version": 1, "pairs": []}
        people = {"schema_version": 1, "people": []}
        arxiv_store = normalized_store({
            **empty_store(),
            "suggestions": [{
                "arxiv_id": "2608.01234",
                "title": "A New Function Field Result",
                "authors": ["Hung-Chun Tsui"],
                "published": "2026-08-03T00:00:00Z",
            }],
        })
        after = copy.deepcopy(arxiv_store)
        after["ignored_ids"] = ["2608.01234"]
        after["suggestions"] = []
        history = empty_history()
        action, entry_id = apply_special(
            data,
            translations,
            history,
            {"op": "arxiv_suggestions", "before": copy.deepcopy(arxiv_store), "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest-1",
            people=people,
            arxiv_store=arxiv_store,
        )
        self.assertEqual((action, entry_id), ("arxiv_suggestions", "arxiv-suggestions"))
        self.assertEqual(arxiv_store["ignored_ids"], ["2608.01234"])
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
            arxiv_store=arxiv_store,
        )
        self.assertEqual((undo_action, undo_id), ("undo", "arxiv-suggestions"))
        self.assertEqual(arxiv_store["ignored_ids"], [])


class StaticArxivUiTests(unittest.TestCase):
    def test_notification_button_is_inserted_before_guide(self) -> None:
        script = (ROOT / "admin/notifications.js").read_text(encoding="utf-8")
        for marker in (
            "data-notification-button",
            "actions.insertBefore(button,guide)",
            "加入新增草稿",
            "忽略",
            "arxivSuggestionsOperation",
            "arXiv metadata 來自 arXiv",
        ):
            self.assertIn(marker, script)

    def test_bibtex_toggle_uses_publication_button_style(self) -> None:
        css = (ROOT / "assets/style.css").read_text(encoding="utf-8")
        self.assertIn(".pub-links .pub-bibtex-toggle", css)
        self.assertIn(".home-publications .pub-links .pub-bibtex-toggle", css)

    def test_weekly_workflow_and_admin_script_are_wired(self) -> None:
        workflow = (ROOT / ".github/workflows/check-arxiv.yml").read_text(encoding="utf-8")
        admin = (ROOT / "admin/index.html").read_text(encoding="utf-8")
        self.assertIn('timezone: "Asia/Tokyo"', workflow)
        self.assertIn("python3 tools/check_arxiv.py", workflow)
        self.assertIn('<script src="notifications.js"></script>', admin)


if __name__ == "__main__":
    unittest.main()
