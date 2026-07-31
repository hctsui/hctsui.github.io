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

from build_cv import build_sections, render_education, render_publication, rich_to_latex  # noqa: E402
from build_site import render_activity, render_category, render_home_sections, render_teaching  # noqa: E402
from category_config import (  # noqa: E402
    all_items,
    categories_for_page,
    migrate_category_data,
    normalized_pages,
    validate_category_data,
)
from process_batch_request import (  # noqa: E402
    apply_content,
    apply_special,
    apply_undo,
    empty_history,
    layout_bundle,
    parse_body,
    rebase_order,
)
from process_request import _compose_visit_description, strip_invisible_chars  # noqa: E402
from homepage_config import (  # noqa: E402
    homepage_activities,
    homepage_publications,
    normalized_homepage_config,
)
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
            "Sendai, Japan · Research visit · Supported by NSTC through Overseas Research Program",
        )
        self.assertEqual(
            _compose_visit_description("仙台", "日本", "研究訪問", "國科會", "千里馬計畫", "zh"),
            "仙台, 日本 · 研究訪問 · 本次訪問經費由國科會透過千里馬計畫提供",
        )


class CategoryArchitectureTests(unittest.TestCase):
    def test_homepage_publications_support_latest_oldest_and_manual_order(self) -> None:
        data = minimal_site()
        data["publications"] = [
            {"id": "old", "type": "publication", "date": "2024-01-01"},
            {"id": "middle", "type": "publication", "date": "2025-01-01"},
            {"id": "new", "type": "publication", "date": "2026-01-01"},
        ]
        data["settings"]["homepage"] = {
            "publications": {"mode": "latest", "limit": 2, "selected_ids": []},
            "activities": {"mode": "manual", "limit": 1, "selected_ids": []},
        }
        self.assertEqual([item["id"] for item in homepage_publications(data)], ["new", "middle"])
        data["settings"]["homepage"]["publications"].update(mode="oldest", limit=1)
        self.assertEqual([item["id"] for item in homepage_publications(data)], ["old"])
        data["settings"]["homepage"]["publications"].update(
            mode="manual", selected_ids=["middle", "new"]
        )
        self.assertEqual([item["id"] for item in homepage_publications(data)], ["middle", "new"])

    def test_homepage_activities_support_manual_order_and_hide_finished_items(self) -> None:
        data = minimal_site()
        data["activities"] = [
            {"id": "past", "type": "conference", "start_date": "2026-01-01", "end_date": "2026-01-02"},
            {"id": "near", "type": "conference", "start_date": "2026-08-01", "end_date": "2026-08-01"},
            {"id": "far", "type": "conference", "start_date": "2026-12-01", "end_date": "2026-12-02"},
        ]
        data["settings"]["homepage"] = {
            "publications": {"mode": "latest", "limit": 2, "selected_ids": []},
            "activities": {
                "mode": "manual",
                "limit": 3,
                "selected_ids": ["far", "past", "near"],
            },
        }
        self.assertEqual(
            [item["id"] for item in homepage_activities(data, date(2026, 7, 31))],
            ["far", "near"],
        )
        data["settings"]["homepage"]["activities"].update(
            mode="soonest", limit=1
        )
        self.assertEqual(
            [item["id"] for item in homepage_activities(data, date(2026, 7, 31))],
            ["near"],
        )

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

    def test_custom_page_color_and_paths_are_preserved(self) -> None:
        data = minimal_site()
        data["settings"]["pages"].append(
            {
                "id": "algebra-i",
                "name": {"en": "Algebra I", "zh": "代數（一）"},
                "path": {"en": "ignored.html", "zh": "ignored-zh.html"},
                "header": {
                    "label": {"en": "Course", "zh": "課程"},
                    "title": {"en": "Algebra I", "zh": "代數（一）"},
                    "intro": {"en": "Course information", "zh": "課程資訊"},
                },
                "color": "#123456",
                "order": 5,
            }
        )
        pages = {page["id"]: page for page in normalized_pages(data)}
        self.assertEqual(pages["algebra-i"]["path"], {"en": "algebra-i.html", "zh": "zh/algebra-i.html"})
        self.assertEqual(pages["algebra-i"]["color"], "#123456")
        validate_category_data(data)

    def test_teaching_optional_page_and_notes_render_as_buttons(self) -> None:
        data = minimal_site()
        entry = {
            "id": "teaching-example",
            "type": "teaching",
            "term": {"en": "Fall 2026", "zh": "2026 秋"},
            "course": {"en": "MATH 101 Algebra", "zh": "MATH 101 代數"},
            "role": {"en": "Lecturer", "zh": "講師"},
            "course_page_id": "cv",
            "lecture_notes_title": {"en": "Lecture Notes", "zh": "講義"},
            "lecture_notes_url": "https://example.com/notes.pdf",
        }
        rendered_en = render_teaching(data, entry, "en")
        rendered_zh = render_teaching(data, entry, "zh")
        self.assertIn('<div class="item-links">', rendered_en)
        self.assertIn('href="cv.html">Course Information</a>', rendered_en)
        self.assertIn('href="cv.html">課程資訊</a>', rendered_zh)
        self.assertIn(">Lecture Notes</a>", rendered_en)
        self.assertIn(">講義</a>", rendered_zh)

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
        rendered = render_activity(entry, "en")
        self.assertIn('<p class="activity-role"><span>Role</span>Speaker</p>', rendered)
        self.assertNotIn("<h3>Example<span", rendered)

    def test_talk_slides_use_the_same_button_group_as_publication_links(self) -> None:
        entry = {
            "id": "talk-with-slides",
            "type": "talk",
            "start_date": "2026-01-01",
            "end_date": "2026-01-01",
            "title": {"en": "Example Talk", "zh": "範例演講"},
            "slides_url": "https://example.com/slides.pdf",
        }
        rendered_en = render_activity(entry, "en")
        rendered_zh = render_activity(entry, "zh")
        self.assertIn('<div class="item-links"><a class="activity-link"', rendered_en)
        self.assertIn(">Slides</a></div>", rendered_en)
        self.assertIn(">投影片</a></div>", rendered_zh)

    def test_home_keeps_legacy_two_column_overview_and_links(self) -> None:
        data = minimal_site()
        data["publications"].append(
            {
                "id": "publication-example",
                "type": "publication",
                "category_id": "publication-preprints",
                "group_id": "preprints",
                "order": 0,
                "date": "2026-01-01",
                "year": 2026,
                "title": {"en": "Example Paper", "zh": "範例論文"},
                "authors": {"en": "Author", "zh": "作者"},
                "venue": {"en": "Preprint", "zh": "預印本"},
                "links": [],
            }
        )
        data["activities"].append(
            {
                "id": "conference-upcoming",
                "type": "conference",
                "category_id": "activity-conferences",
                "order": 0,
                "start_date": "2026-12-01",
                "end_date": "2026-12-01",
                "show_upcoming": True,
                "title": {"en": "Upcoming Meeting", "zh": "近期會議"},
            }
        )
        categories = categories_for_page(data, "home")
        rendered = render_home_sections(data, categories, "en", date(2026, 1, 1))
        self.assertEqual(rendered.count('class="home-overview"'), 1)
        self.assertIn('class="container home-overview-grid"', rendered)
        self.assertIn('data-category-id="home-publications"', rendered)
        self.assertIn('data-category-id="home-upcoming"', rendered)
        self.assertIn('id="latest-publications"', rendered)
        self.assertIn('href="publications.html">All publications →</a>', rendered)
        self.assertIn('href="activities.html">All activities →</a>', rendered)

    def test_home_contact_keeps_public_anchor_and_split_layout(self) -> None:
        data = minimal_site()
        rendered = render_home_sections(
            data,
            categories_for_page(data, "home"),
            "zh",
            date(2026, 1, 1),
        )
        self.assertIn('data-category-id="home-contact" id="contact"', rendered)
        self.assertIn('class="container split"', rendered)
        self.assertIn('href="publications.html">所有論文 →</a>', rendered)
        self.assertIn('href="activities.html">所有活動 →</a>', rendered)


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

    def test_publication_and_teaching_use_page_heading_then_group_heading(self) -> None:
        data = minimal_site()
        data["settings"]["content_groups"]["teaching"].append(
            {"id": "national-tsing-hua-university", "label": {"en": "National Tsing Hua University", "zh": "國立清華大學"}, "order": 0}
        )
        data["settings"]["categories"].append(
            {
                "id": "teaching-national-tsing-hua-university",
                "page_id": "teaching",
                "kind": "teaching",
                "label": {"en": "Institution", "zh": "機構"},
                "title": {"en": "National Tsing Hua University", "zh": "國立清華大學"},
                "intro": {"en": "", "zh": ""},
                "order": 0,
                "show_on_web": True,
                "show_on_cv": True,
            }
        )
        data["publications"].append(
            {
                "id": "publication-example",
                "type": "publication",
                "category_id": "publication-preprints",
                "group_id": "preprints",
                "order": 0,
                "date": "2025-01-01",
                "year": 2025,
                "title": {"en": "A Long Paper Title", "zh": "很長的論文標題"},
                "authors": {"en": "Author", "zh": "作者"},
                "venue": {"en": "Preprint", "zh": "預印本"},
                "links": [{"label": {"en": "arXiv", "zh": "arXiv"}, "url": "https://arxiv.org/abs/1234.5678"}],
            }
        )
        data["teaching"].append(
            {
                "id": "teaching-example",
                "type": "teaching",
                "category_id": "teaching-national-tsing-hua-university",
                "group_id": "national-tsing-hua-university",
                "order": 0,
                "course": {"en": "MATH 123456: A Very Long Course Name", "zh": "MATH 123456：很長的課程名稱"},
                "term": {"en": "Fall 2025", "zh": "2025 秋"},
                "role": {"en": "Teaching Assistant", "zh": "助教"},
                "institution": {"en": "National Tsing Hua University", "zh": "國立清華大學"},
            }
        )
        migrate_category_data(data)
        sections = build_sections(data, "en", date(2026, 1, 1))
        self.assertIn(r"\section{Publications and Preprints}", sections)
        self.assertIn(r"\cvgroup{Preprints}", sections)
        self.assertNotIn(r"\section{Preprints}", sections)
        self.assertIn(r"\section{Teaching Experience}", sections)
        self.assertIn(r"\cvgroup{National Tsing Hua University}", sections)
        self.assertNotIn(r"\section{National Tsing Hua University}", sections)

    def test_upcoming_and_ongoing_activities_are_excluded_until_finished(self) -> None:
        data = minimal_site()
        data["activities"] = [
            {"id": "past", "type": "conference", "category_id": "activity-conferences", "order": 0, "start_date": "2026-06-01", "end_date": "2026-06-02", "title": {"en": "Past Meeting", "zh": "過去會議"}},
            {"id": "today", "type": "conference", "category_id": "activity-conferences", "order": 1, "start_date": "2026-07-31", "end_date": "2026-07-31", "title": {"en": "Today Meeting", "zh": "今日會議"}},
            {"id": "future", "type": "conference", "category_id": "activity-conferences", "order": 2, "start_date": "2026-08-01", "end_date": "2026-08-02", "title": {"en": "Future Meeting", "zh": "未來會議"}},
        ]
        migrate_category_data(data)
        sections = build_sections(data, "en", date(2026, 7, 31))
        self.assertIn("Past Meeting", sections)
        self.assertNotIn("Today Meeting", sections)
        self.assertNotIn("Future Meeting", sections)

    def test_cv_links_and_dates_use_dedicated_lines_and_nonbreaking_dates(self) -> None:
        publication = {
            "title": {"en": "A Long Title"},
            "authors": {"en": "Author"},
            "year": 2026,
            "links": [{"label": {"en": "PDF"}, "url": "https://example.com/paper.pdf"}],
        }
        rendered_publication = render_publication(publication, 1, "en")
        self.assertIn(r"{(1)} \textbf{A Long Title}\\{\small\color{secondaryColor}", rendered_publication)
        self.assertIn(r"\begin{pub}{Author}", rendered_publication)
        education = {
            "title": {"zh": "數學學士"},
            "organization": {"zh": "國立清華大學"},
            "date_label": {"zh": "2021 年 9 月至 2024 年 12 月"},
        }
        rendered_education = render_education(education, "zh")
        self.assertIn(r"{2021 年 9 月至 2024 年 12 月}", rendered_education)


class AdminDocumentationTests(unittest.TestCase):
    def test_admin_links_to_detailed_guide(self) -> None:
        admin = (ROOT / "admin" / "index.html").read_text(encoding="utf-8")
        guide = (ROOT / "admin" / "guide.html").read_text(encoding="utf-8")
        self.assertIn('href="guide.html"', admin)
        for heading in ("標準工作流程", "欄位、小標註與自動填寫", "排序、頁面與類別", "10. 還原", "疑難排解", "送出前完整檢查"):
            self.assertIn(heading, guide)

    def test_required_translation_terms_are_canonical(self) -> None:
        site = json.loads((ROOT / "content" / "site.json").read_text(encoding="utf-8"))
        translations = json.loads((ROOT / "content" / "translations.json").read_text(encoding="utf-8"))
        serialized = json.dumps(site, ensure_ascii=False)
        self.assertNotIn("q-shuffle 關係", serialized)
        self.assertNotIn("v-adic Gamma", serialized)
        pairs = {(row["en"], row["zh"]) for row in translations["pairs"]}
        self.assertIn(("q-shuffle", "q-洗牌"), pairs)
        self.assertIn(("v-adic", "v-進"), pairs)


class BatchOperationTests(unittest.TestCase):
    def test_homepage_operation_is_saved_to_history(self) -> None:
        data = minimal_site()
        data["publications"] = [
            {"id": "paper-1", "type": "publication", "date": "2026-01-01"}
        ]
        before = normalized_homepage_config(data)
        after = copy.deepcopy(before)
        after["publications"] = {
            "mode": "manual",
            "limit": 1,
            "selected_ids": ["paper-1"],
        }
        history = empty_history()
        action, entry_id = apply_special(
            data,
            {"schema_version": 2, "tags": [], "pairs": []},
            history,
            {"op": "homepage", "before": before, "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest",
        )
        self.assertEqual((action, entry_id), ("homepage", "homepage"))
        self.assertEqual(data["settings"]["homepage"]["publications"]["selected_ids"], ["paper-1"])
        self.assertEqual(history["operations"][-1]["action"], "homepage")
        undo_action, undo_id = apply_undo(
            data,
            {"schema_version": 2, "tags": [], "pairs": []},
            history,
            {"op": "undo", "history_id": "issue-1-op-1"},
            "issue-2-op-1",
            2,
            datetime.now(timezone.utc),
            "undo-digest",
        )
        self.assertEqual((undo_action, undo_id), ("undo", "homepage"))
        self.assertEqual(normalized_homepage_config(data), before)
        self.assertEqual(history["operations"][0]["reverted_by"], "issue-2-op-1")

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

    def test_layout_operation_adds_custom_page_and_category(self) -> None:
        data = minimal_site()
        before = layout_bundle(data)
        after = copy.deepcopy(before)
        after["pages"].append(
            {
                "id": "algebra-i",
                "name": {"en": "Algebra I", "zh": "代數（一）"},
                "path": {"en": "algebra-i.html", "zh": "zh/algebra-i.html"},
                "header": {
                    "label": {"en": "Course", "zh": "課程"},
                    "title": {"en": "Algebra I", "zh": "代數（一）"},
                    "intro": {"en": "", "zh": ""},
                },
                "color": "#123456",
                "order": len(after["pages"]),
            }
        )
        after["categories"].append(
            {
                "id": "algebra-i-materials",
                "page_id": "algebra-i",
                "kind": "generic",
                "label": {"en": "Materials", "zh": "教材"},
                "title": {"en": "Course Materials", "zh": "課程教材"},
                "intro": {"en": "", "zh": ""},
                "order": 0,
                "show_on_web": True,
                "show_on_cv": False,
            }
        )
        action, entry_id = apply_special(
            data,
            {"schema_version": 2, "tags": [], "pairs": []},
            empty_history(),
            {"op": "layout", "before": before, "after": after},
            "issue-1-op-1",
            1,
            datetime.now(timezone.utc),
            "digest",
        )
        self.assertEqual((action, entry_id), ("layout", "layout"))
        self.assertIn("algebra-i", {page["id"] for page in normalized_pages(data)})
        self.assertIn("algebra-i-materials", {category["id"] for category in data["settings"]["categories"]})

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


class AdminCompatibilityTests(unittest.TestCase):
    def test_layout_extension_handles_both_initialization_orders(self) -> None:
        script = (ROOT / "admin" / "layout-v2.js").read_text(encoding="utf-8")
        self.assertIn("const baseLoadOrder=loadOrder;", script)
        self.assertIn("if($('#layoutOrderPage')){renderUnifiedOrder();return}", script)
        self.assertIn("setupUnifiedOrderUI();\nif(site)renderAll();", script)
        self.assertIn('id="layoutManagerPage"', script)
        self.assertIn("layoutManagerPageId=event.target.value", script)
        self.assertIn("selectedPage?", script)

    def test_legacy_admin_tools_remain_available(self) -> None:
        page = (ROOT / "admin" / "index.html").read_text(encoding="utf-8")
        for tab in ("catalog", "add", "order", "trash", "homepage", "dictionary", "draft"):
            self.assertIn(f'data-tab="{tab}"', page)
        self.assertNotIn('data-tab="headings"', page)
        self.assertIn('const ADD_TYPES = [', page)
        self.assertIn('"page",\n        "category",\n        "publication"', page)
        for item_type in ("conference", "talk", "visit", "honor", "publication", "teaching"):
            self.assertIn(f'"{item_type}"', page)
        self.assertIn('<script src="tags-v1.js"></script>', page)
        self.assertIn('<script src="layout-v2.js"></script>', page)
        self.assertIn('<script src="homepage-v1.js"></script>', page)
        homepage = (ROOT / "admin" / "homepage-v1.js").read_text(encoding="utf-8")
        for mode in ("latest", "oldest", "manual", "soonest", "farthest"):
            self.assertIn(f"'{mode}'", homepage)
        self.assertIn("data-home-up", homepage)
        self.assertIn("HOMEPAGE_DRAFT_KEY", homepage)


if __name__ == "__main__":
    unittest.main()
