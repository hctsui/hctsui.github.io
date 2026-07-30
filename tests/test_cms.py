from __future__ import annotations

import base64
import copy
import gzip
import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_cv import build_sections, rich_to_latex  # noqa: E402
from build_site import render_activity, render_category  # noqa: E402
from category_config import (  # noqa: E402
    all_items,
    categories_for_page,
    migrate_category_data,
    validate_category_data,
)
from process_batch_request import (  # noqa: E402
    apply_content,
    apply_special,
    empty_history,
    layout_bundle,
    parse_body,
    rebase_order,
)
from process_request import _compose_visit_description, strip_invisible_chars  # noqa: E402
from translation_validation import validate_translation_data  # noqa: E402


def minimal_site() -> dict:
    return migrate_category_data(
        {
            "schema_version": 2,
            "settings": {"content_groups": {"publication": [], "teaching": []}},
            "activities": [],
            "honors": [],
            "publications": [],
            "teaching": [],
            "profile_items": [],
        }
    )


class TranslationValidationTests(unittest.TestCase):
    def test_exact_duplicate_is_rejected(self) -> None:
        data = {"schema_version": 1, "pairs": [{"en": "Number Theory", "zh": "數論"}, {"en": "Number Theory", "zh": "數論"}]}
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_translation_data(data)

    def test_nfkc_duplicate_is_rejected(self) -> None:
        data = {"schema_version": 1, "pairs": [{"en": "ABC", "zh": "測試"}, {"en": "ＡＢＣ", "zh": "測試"}]}
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_translation_data(data)

    def test_tagged_dictionary_is_accepted(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [{"id": "city", "label": {"en": "City", "zh": "城市"}}, {"id": "taiwan", "label": {"en": "Taiwan", "zh": "臺灣"}}],
            "pairs": [{"tags": ["city", "taiwan"], "en": "Tainan", "zh": "臺南"}],
        }
        self.assertEqual(len(validate_translation_data(data)), 1)

    def test_missing_tags_are_assigned_to_other(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [{"id": "other", "label": {"en": "Other", "zh": "其他"}}],
            "pairs": [{"tags": [], "en": "Example", "zh": "範例"}],
        }
        validate_translation_data(data)
        self.assertEqual(data["pairs"][0]["tags"], ["other"])

    def test_unknown_pair_tag_is_rejected(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [{"id": "city", "label": {"en": "City", "zh": "城市"}}],
            "pairs": [{"tags": ["missing"], "en": "Tainan", "zh": "臺南"}],
        }
        with self.assertRaisesRegex(ValueError, "unknown tag"):
            validate_translation_data(data)


class PayloadAndVisitTests(unittest.TestCase):
    def test_invisible_formatting_characters_are_removed(self) -> None:
        dirty = {"title": {"en": "\u200bMeeting\u2060", "zh": "會議\ufeff"}, "items": ["soft\u00adhyphen"]}
        self.assertEqual(
            strip_invisible_chars(dirty),
            {"title": {"en": "Meeting", "zh": "會議"}, "items": ["softhyphen"]},
        )
        self.assertNotIn("\u200b", rich_to_latex("\u200bThe Meeting"))

    def test_compressed_payload_is_decoded(self) -> None:
        payload = {"schema_version": 2, "operations": [{"op": "undo", "history_id": "x"}]}
        encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
        self.assertEqual(parse_body(f"gzip-base64:{encoded}"), payload)

    def test_visit_funding_is_added_to_description(self) -> None:
        self.assertEqual(
            _compose_visit_description("Sendai", "Japan", "Research visit", "NSTC", "Overseas Research Program", "en"),
            "Sendai, Japan · Research visit · Supported by NSTC through Overseas Research Program.",
        )
        self.assertEqual(
            _compose_visit_description("仙台", "日本", "研究訪問", "國科會", "千里馬計畫", "zh"),
            "仙台, 日本 · 研究訪問 · 本次訪問經費由國科會透過千里馬計畫提供。",
        )


class CategoryArchitectureTests(unittest.TestCase):
    def test_every_item_has_a_category_including_profile_items(self) -> None:
        data = minimal_site()
        validate_category_data(data)
        kinds = {item["type"] for item in data["profile_items"]}
        self.assertIn("interest", kinds)
        self.assertIn("education", kinds)
        self.assertTrue(all(item.get("category_id") for item in all_items(data)))

    def test_profile_item_deletion_is_not_undone_by_migration(self) -> None:
        data = minimal_site()
        target = next(item for item in data["profile_items"] if item["type"] == "interest")
        data["profile_items"] = [item for item in data["profile_items"] if item["id"] != target["id"]]
        migrate_category_data(data)
        self.assertFalse(any(item["id"] == target["id"] for item in data["profile_items"]))

    def test_moving_category_moves_its_items_to_another_page(self) -> None:
        data = minimal_site()
        category = next(c for c in data["settings"]["categories"] if c["id"] == "cv-research")
        category["page_id"] = "activities"
        validate_category_data(data)
        self.assertIn("cv-research", [c["id"] for c in categories_for_page(data, "activities")])
        self.assertTrue(all(item["category_id"] == "cv-research" for item in data["profile_items"] if item["type"] == "interest"))

    def test_conference_and_organization_are_independent(self) -> None:
        data = minimal_site()
        data["activities"] = [
            {"id": "conference-1", "type": "conference", "category_id": "activity-conferences", "order": 0, "start_date": "2026-01-01", "end_date": "2026-01-01", "title": {"en": "Conference", "zh": "會議"}},
            {"id": "organization-1", "type": "organization", "category_id": "activity-organization", "order": 0, "start_date": "2026-01-01", "end_date": "2026-01-01", "title": {"en": "Seminar", "zh": "研討會"}, "organization_kind": {"en": "Seminar", "zh": "研討會"}, "role": {"en": "Organizer", "zh": "主辦人"}},
        ]
        migrate_category_data(data)
        self.assertNotIn("show_in_organization", data["activities"][0])
        self.assertEqual(sum(x["type"] == "organization" for x in data["activities"]), 1)

    def test_empty_category_is_hidden_and_conference_role_is_shown(self) -> None:
        data = minimal_site()
        category = next(c for c in data["settings"]["categories"] if c["id"] == "activity-organization")
        self.assertEqual(render_category(data, category, "en", date(2026, 1, 1), 0), "")
        entry = {"id": "c", "type": "conference", "start_date": "2026-01-01", "end_date": "2026-01-01", "title": {"en": "Example", "zh": "範例"}, "role": {"en": "Speaker", "zh": "講者"}}
        self.assertIn('class="activity-role">Speaker</span>', render_activity(entry, "en"))


class CvRenderingTests(unittest.TestCase):
    def test_heading_math_mode_is_preserved_in_chinese_cv(self) -> None:
        rendered = rich_to_latex("正特徵下的 $t$-模與 [i]L[/i]-函數")
        self.assertIn("$t$", rendered)
        self.assertIn("$L$", rendered)
        self.assertNotIn(r"\$t\$", rendered)
        recovered = rich_to_latex("正特徵的 u-多重 zeta 值與 Gamma 函數", auto_math=True)
        self.assertIn("$u$", recovered)
        self.assertIn(r"$\zeta$", recovered)
        self.assertIn(r"$\Gamma$", recovered)

    def test_cv_uses_managed_category_order(self) -> None:
        data = minimal_site()
        category = next(c for c in data["settings"]["categories"] if c["id"] == "cv-research")
        category["title"]["zh"] = "正特徵下的 $t$-模"
        sections = build_sections(data, "zh")
        self.assertIn(r"\section{正特徵下的 $t$-模}", sections)
        self.assertIn("函數體算術", sections)


class BatchOperationTests(unittest.TestCase):
    def test_organization_entry_can_be_added(self) -> None:
        data = minimal_site()
        after = {"id": "organization-1", "type": "organization", "category_id": "activity-organization", "order": 0, "start_date": "2026-01-01", "end_date": "2026-01-01", "title": {"en": "Number Theory Seminar", "zh": "數論研討會"}, "organization_kind": {"en": "Seminar", "zh": "研討會"}, "role": {"en": "Organizer", "zh": "主辦人"}}
        action, entry_id = apply_content(data, empty_history(), {"op": "add", "type": "organization", "after": after}, "issue-1-op-1", 1, datetime.now(timezone.utc), "digest")
        self.assertEqual((action, entry_id), ("add", "organization-1"))

    def test_layout_operation_moves_category_and_items(self) -> None:
        data = minimal_site()
        before = layout_bundle(data)
        after = copy.deepcopy(before)
        category = next(c for c in after["categories"] if c["id"] == "cv-research")
        category["page_id"] = "activities"
        category["order"] = 0
        interest_id = next(x["id"] for x in data["profile_items"] if x["type"] == "interest")
        after["assignments"][interest_id]["order"] = 1
        action, entry_id = apply_special(data, {"schema_version": 2, "tags": [{"id": "other", "label": {"en": "Other", "zh": "其他"}}], "pairs": []}, empty_history(), {"op": "layout", "before": before, "after": after}, "issue-1-op-1", 1, datetime.now(timezone.utc), "digest")
        self.assertEqual((action, entry_id), ("layout", "layout"))
        moved = next(c for c in data["settings"]["categories"] if c["id"] == "cv-research")
        self.assertEqual(moved["page_id"], "activities")

    def test_add_id_collision_is_rejected(self) -> None:
        data = minimal_site()
        data["activities"].append({"id": "talk-1", "type": "talk", "category_id": "activity-talks", "order": 0, "title": {"en": "Existing", "zh": ""}})
        op = {"op": "add", "type": "talk", "after": {"id": "talk-1", "type": "talk", "category_id": "activity-talks", "order": 1, "title": {"en": "New", "zh": ""}}}
        with self.assertRaisesRegex(ValueError, "already exists"):
            apply_content(data, empty_history(), op, "issue-1-op-1", 1, datetime.now(timezone.utc), "digest")

    def test_reorder_keeps_entries_added_later(self) -> None:
        current = {"kind": "talk", "entries": ["a", "new", "b", "c"]}
        desired = {"kind": "talk", "entries": ["c", "a", "b"]}
        self.assertEqual(rebase_order(copy.deepcopy(current), desired)["entries"], ["c", "new", "a", "b"])


if __name__ == "__main__":
    unittest.main()
