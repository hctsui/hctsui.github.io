from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import render_404_page, render_site_navigation  # noqa: E402
from category_config import migrate_category_data, normalized_pages  # noqa: E402


def site_with_custom_pages() -> dict:
    data = migrate_category_data(
        {
            "schema_version": 3,
            "settings": {"content_groups": {"publication": [], "teaching": []}},
            "activities": [],
            "honors": [],
            "publications": [],
            "teaching": [],
            "profile_items": [],
        }
    )
    data["settings"]["pages"].extend(
        [
            {
                "id": "visible-page",
                "name": {"en": "Visible Page", "zh": "顯示頁面"},
                "languages": ["en", "zh"],
                "path": {"en": "visible-page.html", "zh": "zh/visible-page.html"},
                "header": {
                    "label": {"en": "Section", "zh": "分類"},
                    "title": {"en": "Visible Page", "zh": "顯示頁面"},
                    "intro": {"en": "", "zh": ""},
                },
                "color": "#123456",
                "show_in_navigation": True,
                "order": 10,
            },
            {
                "id": "hidden-page",
                "name": {"en": "Hidden Page", "zh": "隱藏頁面"},
                "languages": ["en", "zh"],
                "path": {"en": "hidden-page.html", "zh": "zh/hidden-page.html"},
                "header": {
                    "label": {"en": "Section", "zh": "分類"},
                    "title": {"en": "Hidden Page", "zh": "隱藏頁面"},
                    "intro": {"en": "", "zh": ""},
                },
                "color": "#654321",
                "show_in_navigation": False,
                "order": 11,
            },
        ]
    )
    return migrate_category_data(data)


class NavigationManagementTests(unittest.TestCase):
    def test_old_pages_default_to_visible_navigation(self) -> None:
        data = site_with_custom_pages()
        pages = {page["id"]: page for page in normalized_pages(data)}
        self.assertTrue(pages["home"]["show_in_navigation"])
        self.assertTrue(pages["visible-page"]["show_in_navigation"])
        self.assertFalse(pages["hidden-page"]["show_in_navigation"])

    def test_public_navigation_uses_page_setting(self) -> None:
        data = site_with_custom_pages()
        english = render_site_navigation(data, "home", "en")
        chinese = render_site_navigation(data, "home", "zh")
        self.assertIn("Visible Page", english)
        self.assertNotIn("Hidden Page", english)
        self.assertIn("顯示頁面", chinese)
        self.assertNotIn("隱藏頁面", chinese)
        self.assertIn(">English</a>", chinese)
        self.assertIn(">中文</a>", english)

    def test_404_navigation_uses_same_page_setting(self) -> None:
        data = site_with_custom_pages()
        page = render_404_page(data, date(2026, 8, 1))
        self.assertIn("Visible Page", page)
        self.assertNotIn("Hidden Page", page)
        self.assertIn(">English</button>", page)
        self.assertNotIn(">EN</button>", page)

    def test_admin_exposes_navigation_checkbox(self) -> None:
        script = (ROOT / "admin" / "layout.js").read_text(encoding="utf-8")
        self.assertIn('data-page-field="show_in_navigation"', script)
        self.assertIn("顯示於導覽列", script)


if __name__ == "__main__":
    unittest.main()
