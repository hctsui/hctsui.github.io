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

from process_batch_request import apply_content, empty_history, parse_body, rebase_order  # noqa: E402
from process_request import _compose_visit_description  # noqa: E402
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
            _compose_visit_description("Sendai", "Japan", "Research visit", "NSTC", "en"),
            "Sendai, Japan · Research visit · Supported by NSTC.",
        )
        self.assertEqual(
            _compose_visit_description("仙台", "日本", "研究訪問", "國科會", "zh"),
            "仙台, 日本 · 研究訪問 · 本次訪問獲國科會支持。",
        )


class BatchOperationTests(unittest.TestCase):
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
