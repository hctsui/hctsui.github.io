from __future__ import annotations

import base64
import copy
import gzip
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from process_batch_request import apply_content, apply_special, empty_history, parse_body, rebase_order  # noqa: E402
from process_request import _compose_visit_description, migrate_data  # noqa: E402
from build_site import organization_section, render_activity  # noqa: E402
from build_cv import cv_organization_section  # noqa: E402
from heading_config import HEADING_DEFAULTS, normalized_headings  # noqa: E402
from translation_validation import validate_translation_data  # noqa: E402


class TranslationValidationTests(unittest.TestCase):
    def test_exact_duplicate_is_rejected(self) -> None:
        data = {
            "schema_version": 1,
            "pairs": [
                {"en": "Number Theory", "zh": "數論"},
                {"en": "Number Theory", "zh": "數論"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_translation_data(data)

    def test_nfkc_duplicate_is_rejected(self) -> None:
        data = {
            "schema_version": 1,
            "pairs": [
                {"en": "ABC", "zh": "測試"},
                {"en": "ＡＢＣ", "zh": "測試"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_translation_data(data)

    def test_tagged_dictionary_is_accepted(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [
                {"id": "city", "label": {"en": "City", "zh": "城市"}},
                {"id": "taiwan", "label": {"en": "Taiwan", "zh": "臺灣"}},
            ],
            "pairs": [
                {"tags": ["city", "taiwan"], "en": "Tainan", "zh": "臺南"},
            ],
        }
        self.assertEqual(len(validate_translation_data(data)), 1)

    def test_missing_tags_are_assigned_to_other(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [
                {"id": "other", "label": {"en": "Other", "zh": "其他"}},
                {"id": "city", "label": {"en": "City", "zh": "城市"}},
            ],
            "pairs": [
                {"tags": [], "en": "Example", "zh": "範例"},
            ],
        }
        validate_translation_data(data)
        self.assertEqual(data["pairs"][0]["tags"], ["other"])

    def test_unknown_pair_tag_is_rejected(self) -> None:
        data = {
            "schema_version": 2,
            "tags": [
                {"id": "city", "label": {"en": "City", "zh": "城市"}},
            ],
            "pairs": [
                {"tags": ["missing"], "en": "Tainan", "zh": "臺南"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "unknown tag"):
            validate_translation_data(data)


class PayloadAndVisitTests(unittest.TestCase):
    def test_compressed_payload_is_decoded(self) -> None:
        payload = {"schema_version": 2, "operations": [{"op": "undo", "history_id": "x"}]}
        encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode("utf-8"))).decode("ascii")
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
        self.assertEqual(
            _compose_visit_description("Sendai", "Japan", "", "", "Overseas Research Program", "en"),
            "Sendai, Japan · Supported through Overseas Research Program.",
        )
        self.assertEqual(
            _compose_visit_description("仙台", "日本", "", "", "千里馬計畫", "zh"),
            "仙台, 日本 · 本次訪問由千里馬計畫補助。",
        )


class OrganizationRenderingTests(unittest.TestCase):
    def test_empty_organization_section_is_hidden(self) -> None:
        data = {"settings": {"headings": normalized_headings({})}}
        self.assertEqual(organization_section(data, [], "en"), "")
        self.assertEqual(organization_section(data, [], "zh"), "")
        self.assertEqual(cv_organization_section(data, [], "en"), "")

    def test_organization_section_uses_requested_headings(self) -> None:
        entry = {
            "id": "organization-test",
            "type": "organization",
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "title": {"en": "Number Theory Seminar", "zh": "數論研討會"},
            "organization_kind": {"en": "Seminar", "zh": "研討會"},
            "role": {"en": "Organizer", "zh": "主辦人"},
            "description": {"en": "NTHU, Hsinchu, Taiwan", "zh": "國立清華大學, 新竹, 臺灣"},
        }
        data = {"settings": {"headings": normalized_headings({})}}
        en = organization_section(data, [entry], "en")
        zh = organization_section(data, [entry], "zh")
        self.assertIn("Organizing Experience", en)
        self.assertIn('data-heading-part="title">Organization</h2>', en)
        self.assertIn("籌辦經歷", zh)
        self.assertIn('data-heading-part="title">學術活動籌辦</h2>', zh)
        cv = cv_organization_section(data, [entry], "en")
        self.assertIn(r"\section{Organization}", cv)
        self.assertIn("Number Theory Seminar", cv)

    def test_only_conferences_show_role_badges_in_activity_list(self) -> None:
        base = {
            "id": "entry-test",
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "title": {"en": "Example", "zh": "範例"},
            "description": {"en": "Tokyo, Japan", "zh": "東京, 日本"},
            "role": {"en": "Speaker", "zh": "講者"},
        }
        conference = render_activity({**base, "type": "conference"}, "en")
        talk = render_activity({**base, "type": "talk"}, "en")
        self.assertIn('class="activity-role">Speaker</span>', conference)
        self.assertNotIn('class="activity-role"', talk)


class BatchOperationTests(unittest.TestCase):
    def test_organization_entry_can_be_added(self) -> None:
        data = {
            "activities": [],
            "honors": [],
            "publications": [],
            "teaching": [],
        }
        after = {
            "id": "organization-1",
            "type": "organization",
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "title": {"en": "Number Theory Seminar", "zh": "數論研討會"},
            "organization_kind": {"en": "Seminar", "zh": "研討會"},
            "role": {"en": "Organizer", "zh": "主辦人"},
        }
        action, entry_id = apply_content(
            data,
            empty_history(),
            {"op": "add", "type": "organization", "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest",
        )
        self.assertEqual((action, entry_id), ("add", "organization-1"))
        self.assertEqual(data["activities"][0]["type"], "organization")

    def test_headings_operation_updates_settings(self) -> None:
        before = normalized_headings({})
        after = copy.deepcopy(before)
        after["activities_page"]["title"]["en"] = "Academic Activities"
        data = {"settings": {"headings": copy.deepcopy(before)}, "activities": [], "honors": [], "publications": [], "teaching": []}
        action, entry_id = apply_special(
            data,
            {"schema_version": 2, "tags": [{"id": "other", "label": {"en": "Other", "zh": "其他"}}], "pairs": []},
            empty_history(),
            {"op": "headings", "before": before, "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest",
        )
        self.assertEqual((action, entry_id), ("headings", "headings"))
        self.assertEqual(data["settings"]["headings"]["activities_page"]["title"]["en"], "Academic Activities")

    def test_heading_group_labels_survive_migration(self) -> None:
        headings = normalized_headings({})
        data = {
            "settings": {
                "headings": copy.deepcopy(headings),
                "content_groups": {
                    "publication": [
                        {"id": "preprints", "label": {"en": "Preprints", "zh": "預印本"}, "order": 0, "preset": True}
                    ],
                    "teaching": [
                        {"id": "national-tsing-hua-university", "label": {"en": "National Tsing Hua University", "zh": "國立清華大學"}, "order": 0}
                    ],
                },
            },
            "activities": [],
            "honors": [],
            "publications": [{"id": "paper-1", "type": "publication", "group_id": "preprints", "order": 0}],
            "teaching": [
                {
                    "id": "teaching-1",
                    "type": "teaching",
                    "group_id": "national-tsing-hua-university",
                    "institution": {"en": "National Tsing Hua University", "zh": "國立清華大學"},
                    "order": 0,
                }
            ],
        }
        before = {
            "headings": copy.deepcopy(headings),
            "group_labels": {
                "publication": {"preprints": {"en": "Preprints", "zh": "預印本"}},
                "teaching": {"national-tsing-hua-university": {"en": "National Tsing Hua University", "zh": "國立清華大學"}},
            },
        }
        after = copy.deepcopy(before)
        after["group_labels"]["publication"]["preprints"]["en"] = "Working Papers"
        after["group_labels"]["teaching"]["national-tsing-hua-university"]["zh"] = "國立清華大學數學系"
        action, entry_id = apply_special(
            data,
            {"schema_version": 2, "tags": [{"id": "other", "label": {"en": "Other", "zh": "其他"}}], "pairs": []},
            empty_history(),
            {"op": "headings", "before": before, "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest",
        )
        self.assertEqual((action, entry_id), ("headings", "headings"))
        migrate_data(data)
        publication_label = data["settings"]["content_groups"]["publication"][0]["label"]["en"]
        teaching_label = data["settings"]["content_groups"]["teaching"][0]["label"]["zh"]
        self.assertEqual(publication_label, "Working Papers")
        self.assertEqual(teaching_label, "國立清華大學數學系")
        self.assertEqual(data["teaching"][0]["institution"]["zh"], "國立清華大學數學系")

    def test_add_id_collision_is_rejected(self) -> None:
        data = {
            "activities": [
                {
                    "id": "talk-1",
                    "type": "talk",
                    "title": {"en": "Existing", "zh": ""},
                }
            ],
            "honors": [],
            "publications": [],
            "teaching": [],
        }
        op = {
            "op": "add",
            "type": "talk",
            "after": {
                "id": "talk-1",
                "type": "talk",
                "title": {"en": "New", "zh": ""},
            },
        }
        with self.assertRaisesRegex(ValueError, "already exists"):
            apply_content(
                data,
                empty_history(),
                op,
                "issue-1-op-1",
                1,
                datetime.now(timezone.utc),
                "digest",
            )

    def test_reorder_keeps_entries_added_later(self) -> None:
        current = {"kind": "talk", "entries": ["a", "new", "b", "c"]}
        desired = {"kind": "talk", "entries": ["c", "a", "b"]}
        rebased = rebase_order(copy.deepcopy(current), desired)
        self.assertEqual(rebased["entries"], ["c", "new", "a", "b"])


if __name__ == "__main__":
    unittest.main()
