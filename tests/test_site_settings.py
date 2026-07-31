from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import (  # noqa: E402
    apply_cloudflare_analytics,
    apply_seo_metadata,
    render_404_page,
    render_footer,
)
from process_batch_request import apply_special, apply_undo, empty_history  # noqa: E402
from site_settings_config import current_site_settings, normalized_site_settings, validate_site_settings  # noqa: E402


def site_data() -> dict:
    return {
        "settings": {
            "pages": [
                {"id": "home", "name": {"en": "Home", "zh": "首頁"}, "path": {"en": "index.html", "zh": "zh/index.html"}, "header": None},
                {"id": "publications", "name": {"en": "Publications", "zh": "論文"}, "path": {"en": "publications.html", "zh": "zh/publications.html"}, "header": {"title": {"en": "Publications", "zh": "論文"}, "intro": {"en": "Papers", "zh": "論文列表"}}},
            ],
            "categories": [],
        },
        "activities": [], "honors": [], "publications": [], "teaching": [], "profile_items": [],
    }


class SiteSettingsTests(unittest.TestCase):
    def test_defaults_are_backward_compatible(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        self.assertEqual(settings["seo"]["base_url"], "https://hctsui.github.io")
        self.assertEqual(len(settings["footer"]["items"]), 2)
        self.assertFalse(settings["analytics"]["enabled"])
        self.assertEqual(settings["error_page"]["auto_redirect"]["seconds"], 8)
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

    def test_footer_supports_custom_icon_links_alignment_and_placeholders(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["footer"]["items"] = [
            {"id": "left", "text": {"en": "{year} Hung-Chun Tsui", "zh": ""}, "url": "", "icon": "copyright", "custom_icon": "", "alignment": "left", "new_tab": False},
            {"id": "center", "text": {"en": "Project", "zh": ""}, "url": "https://example.com", "icon": "other", "custom_icon": "assets/icons/project.svg", "alignment": "center", "new_tab": True},
            {"id": "right", "text": {"en": "Updated {updated}", "zh": ""}, "url": "", "icon": "none", "custom_icon": "", "alignment": "right", "new_tab": False},
        ]
        data["settings"].update(settings)
        rendered = render_footer(data, "en", date(2026, 8, 1), updated="2026/8/1")
        self.assertIn("footer-left", rendered)
        self.assertIn("footer-center", rendered)
        self.assertIn("footer-right", rendered)
        self.assertIn('class="footer-custom-icon"', rendered)
        self.assertIn('src="https://hctsui.github.io/assets/icons/project.svg"', rendered)
        self.assertIn('target="_blank"', rendered)
        self.assertIn("2026 Hung-Chun Tsui", rendered)
        self.assertIn("Updated 2026/8/1", rendered)

    def test_cloudflare_beacon_is_added_and_removed_idempotently(self) -> None:
        data = site_data()
        source = '<html><head></head><body><main></main></body></html>'
        self.assertNotIn("cloudflare-web-analytics", apply_cloudflare_analytics(source, data))
        data["settings"]["analytics"] = {"enabled": True, "token": "a" * 32}
        rendered = apply_cloudflare_analytics(source, data)
        self.assertIn('type="module"', rendered)
        self.assertIn("static.cloudflareinsights.com/beacon.min.js", rendered)
        self.assertEqual(rendered.count("managed:cloudflare-web-analytics"), 2)
        rendered_again = apply_cloudflare_analytics(rendered, data)
        self.assertEqual(rendered_again.count("static.cloudflareinsights.com/beacon.min.js"), 1)
        data["settings"]["analytics"] = {"enabled": False, "token": ""}
        self.assertNotIn("cloudflare-web-analytics", apply_cloudflare_analytics(rendered_again, data))

    def test_404_page_supports_colors_bilingual_content_and_redirect(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["error_page"]["auto_redirect"] = {"enabled": True, "seconds": 12}
        settings["error_page"]["colors"]["accent"] = "#123456"
        data["settings"].update(settings)
        rendered = render_404_page(data, date(2026, 8, 1))
        for marker in (
            '<meta name="robots" content="noindex,nofollow">',
            'data-language="en"',
            'data-language="zh"',
            'data-switch-language',
            '--nf-accent:#123456',
            '"enabled":true,"seconds":12',
        ):
            self.assertIn(marker, rendered)

    def test_site_settings_batch_and_undo(self) -> None:
        data = site_data()
        translations = {"schema_version": 1, "pairs": []}
        history = empty_history()
        before = current_site_settings(data)
        after = copy.deepcopy(before)
        after["seo"]["pages"]["home"]["title"]["en"] = "Custom title"
        after["footer"]["items"][0]["alignment"] = "center"
        after["analytics"] = {"schema_version": 1, "enabled": True, "token": "b" * 32}
        after["error_page"]["auto_redirect"] = {"enabled": True, "seconds": 9}
        action, entry = apply_special(data, translations, history, {"op": "site_settings", "before": before, "after": after}, "issue-1-op-1", 1, datetime.now(timezone.utc), "digest", people={"schema_version": 1, "people": []})
        self.assertEqual((action, entry), ("site_settings", "site-settings"))
        current = current_site_settings(data)
        self.assertEqual(current["seo"]["pages"]["home"]["title"]["en"], "Custom title")
        self.assertTrue(current["analytics"]["enabled"])
        self.assertEqual(current["error_page"]["auto_redirect"]["seconds"], 9)
        apply_undo(data, translations, history, {"op": "undo", "history_id": "issue-1-op-1"}, "issue-2-op-1", 2, datetime.now(timezone.utc), "digest-2", people={"schema_version": 1, "people": []})
        self.assertEqual(current_site_settings(data), normalized_site_settings(before, data))

    def test_invalid_enabled_cloudflare_token_is_rejected(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["analytics"] = {"enabled": True, "token": "not-a-token"}
        with self.assertRaises(ValueError):
            validate_site_settings(settings, data)


if __name__ == "__main__":
    unittest.main()
