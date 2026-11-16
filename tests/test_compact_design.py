"""Regression checks for the managed compact public layout."""
from __future__ import annotations

import copy
import re
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import (  # noqa: E402
    category_items, load_data, page_header, render_category,
    render_contact_page_main, render_course_page, render_publication_article,
)
from category_config import categories_for_page, normalized_pages, validate_category_data  # noqa: E402


class CompactDesignTests(unittest.TestCase):
    def test_header_keeps_hc_wordmark_without_favicon_image(self) -> None:
        from build_site import render_site_header

        data = load_data()
        for lang in ("en", "zh"):
            header = render_site_header(data, "home", lang)
            self.assertIn('>HC Tsui</a>', header)
            self.assertNotIn('brand-icon', header)

    def test_new_publication_category_inherits_section_heading_and_jump(self) -> None:
        from category_config import ensure_item_categories

        data = load_data()
        data["settings"]["categories"].append({
            "id": "publication-survey-papers", "page_id": "publications",
            "kind": "publication", "title": {"en": "Survey Papers", "zh": "綜述論文"},
            "intro": {"en": "", "zh": ""}, "order": 10,
            "show_on_web": True, "show_on_cv": True,
        })
        item = copy.deepcopy(data["publications"][0])
        item.update(id="publication-survey-demo", group_id="survey-papers",
                    category_id="publication-survey-papers")
        data["publications"].append(item)
        ensure_item_categories(data)
        today = date(2026, 11, 16)
        for lang, title in (("en", "Survey Papers"), ("zh", "綜述論文")):
            rendered = [(category, render_category(data, category, lang, today, i))
                        for i, category in enumerate(categories_for_page(data, "publications"))]
            section = next(markup for category, markup in rendered
                           if category["id"] == "publication-survey-papers")
            visible = [(category, len(category_items(data, category, today)))
                       for category, markup in rendered if markup]
            self.assertIn(f'<h2 class="section-title">{title}</h2>', section)
            self.assertIn('id="publication-survey-demo"', section)
            self.assertIn(f'href="#publication-survey-papers">{title}',
                          page_header(data, "publications", lang, visible))
        css = (ROOT / "assets" / "compact.css").read_text(encoding="utf-8")
        self.assertIn('.managed-category.section>.container>.section-title', css)

    def test_office_link_survives_profile_sync_and_is_localized(self) -> None:
        from cms_extensions import personal_profile, sync_personal_profile
        from build_site import managed_contact_items, render_contact

        data = load_data()
        profile = personal_profile(data)
        profile["office_url"] = "https://example.org/location"
        sync_personal_profile(data, profile)
        for lang in ("en", "zh"):
            markup = render_contact(managed_contact_items(data), lang)
            self.assertIn('href="https://example.org/location"', markup)
            self.assertIn(profile["office"][lang], markup)
        profile["office_url"] = ""
        sync_personal_profile(data, profile)
        self.assertNotIn('href="https://example.org/location"', render_contact(managed_contact_items(data), "en"))
        profile["office_url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            sync_personal_profile(data, profile)

    def test_chinese_featured_publication_authors_use_chinese_names(self) -> None:
        data = load_data()
        entries = {item["id"]: item for item in data["publications"]}
        journal = render_publication_article(entries["publication-2604004"], "zh", homepage=True)
        collaborative = render_publication_article(entries["publication-2603003"], "zh", homepage=True)
        self.assertIn('<p class="authors"><strong>崔鴻竣</strong></p>', journal)
        authors = collaborative.split('<p class="authors">', 1)[1].split('</p>', 1)[0]
        self.assertIn('<strong>崔鴻竣</strong>', authors)
        self.assertIn('張庭瑋, 陳松筠, 黃斐浚, 崔鴻竣', re.sub(r'<[^>]+>', '', authors))
        self.assertNotIn('Hung-Chun Tsui', authors)

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
        # Keep this category empty even when the live CMS has organization entries.
        data["activities"] = [
            item for item in data["activities"]
            if item.get("category_id") != "activity-organization"
        ]
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
        data = load_data()
        duplicate = copy.deepcopy(next(x for x in data["profile_items"] if x["id"] == "contact-2600001"))
        duplicate["id"] = "contact-institutional-email"
        data["profile_items"].append(duplicate)
        markup = render_contact_page_main(data, "en")
        self.assertIn("Get in touch", markup)
        self.assertIn("Institutional email", markup)
        self.assertEqual(markup.count('href="mailto:hctsui@gapp.nthu.edu.tw"'), 1)
        self.assertIn('data-contact-mode="worker"', markup)
        self.assertIn('name="botcheck"', markup)
        self.assertIn('class="cf-turnstile"', markup)
        self.assertNotIn("section-label", markup)

    def test_home_contact_deduplicates_legacy_profile_aliases(self) -> None:
        from build_site import render_contact

        data = load_data()
        legacy = next(x for x in data["profile_items"] if x["id"] == "contact-2600001")
        personal = next(x for x in data["profile_items"] if x["id"] == "contact-2600002")
        office = next(x for x in data["profile_items"] if x["id"] == "contact-2600003")
        items = [legacy, dict(legacy, id="contact-institutional-email"),
                 personal, dict(personal, id="contact-personal-email"),
                 office, dict(office, id="contact-address-office")]
        for lang in ("en", "zh"):
            markup = render_contact(items, lang)
            self.assertEqual(markup.count('href="mailto:hctsui@gapp.nthu.edu.tw"'), 1)
            self.assertEqual(markup.count('href="mailto:hctsui.math@gmail.com"'), 1)
            self.assertEqual(markup.count('class="contact-location"'), 1)

    def test_home_contact_form_link_has_directional_cue(self) -> None:
        from build_site import contact_form_home_card

        data = load_data()
        self.assertIn('Fill out<sup aria-hidden="true">↗</sup></a>', contact_form_home_card(data, "en"))
        self.assertIn('填寫<sup aria-hidden="true">↗</sup></a>', contact_form_home_card(data, "zh"))


if __name__ == "__main__":
    unittest.main()
