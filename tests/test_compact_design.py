"""Regression checks for the managed compact public layout."""
from __future__ import annotations

import copy
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import (  # noqa: E402
    category_items, load_data, page_header, render_category,
    render_contact_page_main, render_course_page,
)
from category_config import categories_for_page, normalized_pages, validate_category_data  # noqa: E402


class CompactDesignTests(unittest.TestCase):
    def test_section_links_follow_content_and_admin_order(self) -> None:
        data = load_data()
        rows = data["settings"]["categories"]
        talk = next(row for row in rows if row["id"] == "activity-talks")
        visit = next(row for row in rows if row["id"] == "activity-visits")
        talk["order"], visit["order"] = -1, 1
        rows.append({
            "id": "activity-new", "page_id": "activities", "kind": "generic",
            "title": {"en": "New section", "zh": "新區段"},
            "intro": {"en": "", "zh": ""}, "order": 2,
            "show_on_web": True, "show_on_cv": False,
        })
        data["profile_items"].append({
            "id": "new-item", "type": "generic", "category_id": "activity-new",
            "order": 0, "title": {"en": "A new entry", "zh": "新項目"},
        })
        today = date(2026, 11, 15)
        visible = []
        for index, category in enumerate(categories_for_page(data, "activities")):
            if render_category(data, category, "en", today, index):
                visible.append((category, len(category_items(data, category, today))))
        header = page_header(data, "activities", "en", visible)
        self.assertLess(header.index("#activity-talks"), header.index("#activity-visits"))
        self.assertLess(header.index("#activity-visits"), header.index("#activity-new"))
        self.assertNotIn("#activity-organization", header)  # Empty managed category.
        self.assertIn('href="#activity-new">New section<span class="jump-count">1</span>', header)
        self.assertNotIn("section-label", header)

    def test_custom_page_and_course_need_no_eyebrow(self) -> None:
        data = load_data()
        page = {
            "id": "research-notes", "page_type": "general",
            "name": {"en": "Notes", "zh": "筆記"},
            "path": {"en": "research-notes.html", "zh": "zh/research-notes.html"},
            "header": {"title": {"en": "Notes", "zh": "筆記"}, "intro": {"en": "", "zh": ""}},
            "color": "#2c4758", "languages": ["en", "zh"], "order": 90,
        }
        data["settings"]["pages"].append(page)
        validate_category_data(data)
        self.assertIn("<h1", page_header(data, "research-notes", "zh"))
        course = copy.deepcopy(page)
        course.update(id="course-notes", page_type="course", languages=["en"], path={"en": "teaching/course-notes/index.html", "zh": ""}, course={"details": [], "schedule": []})
        data["settings"]["pages"].append(course)
        validate_category_data(data)
        self.assertIn("Course information will be posted here.", render_course_page(data, course, "en"))

    def test_contact_keeps_worker_and_managed_details(self) -> None:
        markup = render_contact_page_main(load_data(), "en")
        self.assertIn("Get in touch", markup)
        self.assertIn("Institutional email", markup)
        self.assertIn('data-contact-mode="worker"', markup)
        self.assertIn('name="botcheck"', markup)
        self.assertIn('class="cf-turnstile"', markup)
        self.assertNotIn("section-label", markup)


if __name__ == "__main__":
    unittest.main()
