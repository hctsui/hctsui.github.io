from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import apply_seo_metadata, render_footer  # noqa: E402
from process_batch_request import apply_special, apply_undo, empty_history  # noqa: E402
from site_settings_config import current_site_settings, normalized_site_settings, validate_site_settings  # noqa: E402


def site_data() -> dict:
    return {
        "settings": {
            "pages": [
                {"id": "home", "path": {"en": "index.html", "zh": "zh/index.html"}, "header": None},
                {"id": "publications", "path": {"en": "publications.html", "zh": "zh/publications.html"}, "header": {"title": {"en": "Publications", "zh": "論文"}, "intro": {"en": "Papers", "zh": "論文列表"}}},
            ]
        },
        "activities": [], "honors": [], "publications": [], "teaching": [], "profile_items": [],
    }


class SiteSettingsTests(unittest.TestCase):
    def test_defaults_are_backward_compatible(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        self.assertEqual(settings["seo"]["base_url"], "https://hctsui.github.io")
        self.assertEqual(len(settings["footer"]["items"]), 2)
        validate_site_settings(settings, data)

    def test_seo_metadata_contains_canonical_og_twitter_and_alternates(self) -> None:
        data = site_data()
        page = data["settings"]["pages"][1]
        source = '<html><head><title>Old</title></head><body></body></html>'
        rendered = apply_seo_metadata(source, data, page, "en")
        for marker in (
            '<meta name="description"',
            '<link rel="canonical" href="https://hctsui.github.io/publications.html">',
            '<meta property="og:title"',
            '<meta property="og:image"',
            '<meta name="twitter:card" content="summary_large_image">',
            'hreflang="zh"',
        ):
            self.assertIn(marker, rendered)

    def test_footer_supports_three_alignments_icons_links_and_placeholders(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["footer"]["items"] = [
            {"id": "left", "text": {"en": "{year} Hung-Chun Tsui", "zh": ""}, "url": "", "icon": "copyright", "alignment": "left", "new_tab": False},
            {"id": "center", "text": {"en": "Email", "zh": ""}, "url": "mailto:test@example.com", "icon": "email", "alignment": "center", "new_tab": False},
            {"id": "right", "text": {"en": "Updated {updated}", "zh": ""}, "url": "", "icon": "none", "alignment": "right", "new_tab": False},
        ]
        data["settings"]["seo"] = settings["seo"]
        data["settings"]["footer"] = settings["footer"]
        rendered = render_footer(data, "en", date(2026, 8, 1), updated="2026/8/1")
        self.assertIn("footer-left", rendered)
        self.assertIn("footer-center", rendered)
        self.assertIn("footer-right", rendered)
        self.assertIn("mailto:test@example.com", rendered)
        self.assertIn("2026 Hung-Chun Tsui", rendered)
        self.assertIn("Updated 2026/8/1", rendered)

    def test_site_settings_batch_and_undo(self) -> None:
        data = site_data()
        translations = {"schema_version": 1, "pairs": []}
        history = empty_history()
        before = current_site_settings(data)
        after = copy.deepcopy(before)
        after["seo"]["pages"]["home"]["title"]["en"] = "Custom title"
        after["footer"]["items"][0]["alignment"] = "center"
        action, entry = apply_special(data, translations, history, {"op": "site_settings", "before": before, "after": after}, "issue-1-op-1", 1, datetime.now(timezone.utc), "digest", people={"schema_version": 1, "people": []})
        self.assertEqual((action, entry), ("site_settings", "site-settings"))
        self.assertEqual(current_site_settings(data)["seo"]["pages"]["home"]["title"]["en"], "Custom title")
        apply_undo(data, translations, history, {"op": "undo", "history_id": "issue-1-op-1"}, "issue-2-op-1", 2, datetime.now(timezone.utc), "digest-2", people={"schema_version": 1, "people": []})
        self.assertEqual(current_site_settings(data), normalized_site_settings(before, data))


if __name__ == "__main__":
    unittest.main()
