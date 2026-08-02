from __future__ import annotations

import copy
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import (  # noqa: E402
    apply_analytics,
    apply_cloudflare_analytics,
    apply_seo_metadata,
    contact_form_home_card,
    render_404_page,
    render_contact,
    render_contact_form,
    render_contact_page_main,
    render_footer,
    render_robots_txt,
    render_sitemap_xml,
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
        self.assertEqual(settings["analytics"]["tracking_mode"], "off")
        self.assertEqual(settings["error_page"]["auto_redirect"]["seconds"], 8)
        self.assertIn("contact", settings["seo"]["pages"])
        self.assertEqual(settings["contact_form"]["page_design"]["title"]["en"], "Contact Form")
        validate_site_settings(settings, data)

    def test_admin_and_python_contact_defaults_match_for_conflict_check(self) -> None:
        data = site_data()
        before = current_site_settings(data)
        self.assertEqual(
            before["contact_form"]["privacy_note"],
            {
                "en": "Your message will be delivered privately by Web3Forms.",
                "zh": "完整訊息只會透過 Web3Forms 私下寄送，不會存入公開網站資料。",
            },
        )
        admin_before = copy.deepcopy(before)
        after = copy.deepcopy(admin_before)
        after["contact_form"].update({
            "enabled": True,
            "mode": "worker",
            "worker_url": "https://hctsui-contact.example.workers.dev",
        })
        action, entry = apply_special(
            data,
            {"schema_version": 1, "pairs": []},
            empty_history(),
            {"op": "site_settings", "before": admin_before, "after": after},
            "issue-default-parity-op-1",
            1,
            datetime.now(timezone.utc),
            "digest-default-parity",
            people={"schema_version": 1, "people": []},
        )
        self.assertEqual((action, entry), ("site_settings", "site-settings"))
        self.assertEqual(current_site_settings(data)["contact_form"]["worker_url"], "https://hctsui-contact.example.workers.dev")

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

    def test_search_engine_files_include_only_public_pages(self) -> None:
        data = site_data()
        robots = render_robots_txt(data)
        sitemap = render_sitemap_xml(data)
        for path in ("/admin/", "/dossier.html", "/zh/dossier.html", "/content/"):
            self.assertIn(f"Disallow: {path}", robots)
        self.assertIn("Sitemap: https://hctsui.github.io/sitemap.xml", robots)
        for url in (
            "https://hctsui.github.io/", "https://hctsui.github.io/zh/",
            "https://hctsui.github.io/publications.html", "https://hctsui.github.io/zh/publications.html",
            "https://hctsui.github.io/contact.html",
        ):
            self.assertIn(f"<loc>{url}</loc>", sitemap)
        for excluded in ("admin", "dossier", "content"):
            self.assertNotIn(excluded, sitemap)

    def test_footer_supports_custom_icon_links_alignment_and_placeholders(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["footer"]["items"] = [
            {"id": "left", "text": {"en": "{year} Hung-Chun Tsui", "zh": ""}, "url": "", "icon": "copyright", "custom_icon": "", "alignment": "left", "new_tab": False},
            {"id": "center", "text": {"en": "Project", "zh": ""}, "url": "https://example.com", "icon": "other", "custom_icon": "assets/images/project.svg", "alignment": "center", "new_tab": True},
            {"id": "right", "text": {"en": "Updated {updated}", "zh": ""}, "url": "", "icon": "none", "custom_icon": "", "alignment": "right", "new_tab": False},
        ]
        data["settings"].update(settings)
        rendered = render_footer(data, "en", date(2026, 8, 1), updated="2026/8/1")
        self.assertIn("footer-left", rendered)
        self.assertIn("footer-center", rendered)
        self.assertIn("footer-right", rendered)
        self.assertIn('class="footer-custom-icon"', rendered)
        self.assertIn('src="https://hctsui.github.io/assets/images/project.svg"', rendered)
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

    def test_analytics_supports_cloudflare_google_both_and_off(self) -> None:
        data = site_data()
        source = '<html><head></head><body><main></main></body></html>'
        data["settings"]["analytics"] = {
            "tracking_mode": "cloudflare", "cloudflare_token": "c" * 32,
            "google_measurement_id": "G-ABCD1234",
        }
        cloudflare = apply_analytics(source, data)
        self.assertIn("static.cloudflareinsights.com/beacon.min.js", cloudflare)
        self.assertNotIn("googletagmanager.com", cloudflare)
        data["settings"]["analytics"] = {
            "tracking_mode": "google", "cloudflare_token": "c" * 32,
            "google_measurement_id": "G-ABCD1234",
        }
        google = apply_analytics(cloudflare, data)
        self.assertNotIn("static.cloudflareinsights.com/beacon.min.js", google)
        self.assertIn("googletagmanager.com/gtag/js?id=G-ABCD1234", google)
        self.assertIn('gtag("config", "G-ABCD1234")', google)
        self.assertEqual(google.count("managed:google-analytics"), 2)
        data["settings"]["analytics"]["tracking_mode"] = "both"
        both = apply_analytics(google, data)
        self.assertIn("static.cloudflareinsights.com/beacon.min.js", both)
        self.assertIn("googletagmanager.com/gtag/js?id=G-ABCD1234", both)
        self.assertEqual(both.count("static.cloudflareinsights.com/beacon.min.js"), 1)
        self.assertEqual(both.count("googletagmanager.com/gtag/js"), 1)
        data["settings"]["analytics"]["tracking_mode"] = "off"
        disabled = apply_analytics(both, data)
        self.assertNotIn("managed:cloudflare-web-analytics", disabled)
        self.assertNotIn("managed:google-analytics", disabled)

    def test_analytics_connections_survive_mode_switches(self) -> None:
        data = site_data()
        both_configured = current_site_settings(data)
        both_configured["analytics"] = {
            "schema_version": 3, "tracking_mode": "both",
            "cloudflare_token": "e" * 32, "google_measurement_id": "G-ABCD1234",
        }
        normalized = normalized_site_settings(both_configured, data)
        self.assertEqual(normalized["analytics"]["cloudflare_token"], "e" * 32)
        self.assertEqual(normalized["analytics"]["google_measurement_id"], "G-ABCD1234")
        normalized["analytics"]["tracking_mode"] = "off"
        reopened = normalized_site_settings(normalized, data)
        self.assertEqual(reopened["analytics"]["tracking_mode"], "off")
        self.assertEqual(reopened["analytics"]["cloudflare_token"], "e" * 32)
        self.assertEqual(reopened["analytics"]["google_measurement_id"], "G-ABCD1234")

    def test_legacy_cloudflare_token_normalizes_without_reentry(self) -> None:
        data = site_data()
        data["settings"]["analytics"] = {"enabled": True, "token": "d" * 32}
        analytics = current_site_settings(data)["analytics"]
        self.assertEqual(analytics["tracking_mode"], "cloudflare")
        self.assertEqual(analytics["cloudflare_token"], "d" * 32)
        validate_site_settings(current_site_settings(data), data)

    def test_contact_form_modes_are_safe_and_configurable(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        self.assertFalse(settings["contact_form"]["enabled"])
        self.assertEqual(settings["contact_form"]["email_subject"], "[hctsui.github.io] New contact message")
        self.assertEqual(render_contact_form(data, "en"), "")
        settings["contact_form"].update({
            "enabled": True, "mode": "worker",
            "worker_url": "https://contact.example.workers.dev",
            "turnstile_site_key": "site-key-public",
        })
        data["settings"].update(settings)
        rendered = render_contact_form(data, "en")
        self.assertIn('action="https://contact.example.workers.dev"', rendered)
        self.assertIn('class="cf-turnstile"', rendered)
        self.assertIn('data-size="flexible"', rendered)
        self.assertIn('data-sitekey="site-key-public"', rendered)
        self.assertIn('name="email_subject" value="[hctsui.github.io] New contact message"', rendered)
        self.assertIn('name="visitor_subject"', rendered)
        self.assertNotIn('<input name="subject"', rendered)
        self.assertNotIn("TURNSTILE_SECRET", rendered)
        self.assertNotIn("GITHUB_TOKEN", rendered)

    def test_contact_page_design_and_home_entry_are_generated(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["contact_form"].update({
            "enabled": True, "mode": "email_only", "web3forms_access_key": "a" * 32,
        })
        settings["contact_form"]["page_design"]["title"] = {"en": "Write to me", "zh": "聯絡我"}
        settings["contact_form"]["page_design"]["colors"]["accent"] = "#123456"
        data["settings"].update(settings)
        self.assertIn('<div class="contact-form-entry"', contact_form_home_card(data, "en"))
        self.assertIn('href="contact.html">Fill out</a>', contact_form_home_card(data, "en"))
        self.assertIn('href="contact.html">填寫</a>', contact_form_home_card(data, "zh"))
        page = render_contact_page_main(data, "en")
        self.assertIn("Write to me", page)
        self.assertIn('class="contact-form-shell"', page)

    def test_contact_home_grid_inserts_form_after_affiliation_and_keeps_address_full_width(self) -> None:
        items = [
            {"id": "contact-institutional-email", "title": {"en": "Institutional email"}, "description": {"en": "a@example.com"}},
            {"id": "contact-personal-email", "title": {"en": "Personal email"}, "description": {"en": "b@example.com"}},
            {"id": "contact-affiliation", "title": {"en": "Affiliation"}, "description": {"en": "University"}},
            {"id": "contact-address-office", "title": {"en": "Address & office"}, "description": {"en": "Room 1"}},
        ]
        extra = '<div class="contact-form-entry"><span>Contact Form</span><a href="contact.html">Fill out</a></div>'
        rendered = render_contact(items, "en", extra_card=extra)
        self.assertLess(rendered.index("Affiliation"), rendered.index("Contact Form"))
        self.assertLess(rendered.index("Contact Form"), rendered.index("Address &amp; office"))
        self.assertIn('class="contact-location" data-entry-id="contact-address-office"', rendered)

    def test_contact_page_design_requires_bilingual_content(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["contact_form"]["page_design"]["title"]["zh"] = ""
        with self.assertRaisesRegex(ValueError, "Contact page title"):
            validate_site_settings(settings, data)

    def test_incomplete_worker_mode_is_rejected_but_disabled_draft_is_allowed(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["contact_form"].update({"enabled": False, "mode": "worker", "worker_url": ""})
        validate_site_settings(settings, data)
        settings["contact_form"]["enabled"] = True
        with self.assertRaisesRegex(ValueError, "Worker URL is missing or invalid"):
            validate_site_settings(settings, data)

    def test_email_only_contact_form_uses_fixed_subject_and_separate_visitor_subject(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["contact_form"].update({
            "enabled": True, "mode": "email_only", "web3forms_access_key": "a" * 32,
            "email_subject": "[Website] Contact form",
        })
        data["settings"].update(settings)
        rendered = render_contact_form(data, "en")
        self.assertIn('name="subject" value="[Website] Contact form"', rendered)
        self.assertIn('name="visitor_subject"', rendered)
        self.assertIn('name="from_name" value="hctsui.github.io contact form"', rendered)
        self.assertNotIn('<input name="subject" maxlength=', rendered)

    def test_404_page_supports_colors_bilingual_content_and_redirect(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["error_page"]["auto_redirect"] = {"enabled": True, "seconds": 12}
        settings["error_page"]["colors"]["accent"] = "#123456"
        data["settings"].update(settings)
        rendered = render_404_page(data, date(2026, 8, 1))
        for marker in (
            '<meta name="robots" content="noindex,nofollow">', 'data-language="en"',
            'data-language="zh"', 'data-switch-language', '--nf-accent:#123456',
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
        self.assertEqual(current["analytics"]["tracking_mode"], "cloudflare")
        self.assertEqual(current["error_page"]["auto_redirect"]["seconds"], 9)
        apply_undo(data, translations, history, {"op": "undo", "history_id": "issue-1-op-1"}, "issue-2-op-1", 2, datetime.now(timezone.utc), "digest-2", people={"schema_version": 1, "people": []})
        self.assertEqual(current_site_settings(data), normalized_site_settings(before, data))

    def test_stale_site_settings_preserve_unrelated_newer_values(self) -> None:
        data = site_data()
        translations = {"schema_version": 1, "pairs": []}
        before = current_site_settings(data)
        requested = copy.deepcopy(before)
        requested["analytics"].update({"tracking_mode": "google", "google_measurement_id": "G-ABC12345"})
        newer = copy.deepcopy(before)
        newer["seo"]["pages"]["home"]["description"]["en"] = "Updated elsewhere"
        for section in ("general", "footer", "seo", "analytics", "contact_form", "error_page"):
            data["settings"][section] = copy.deepcopy(newer[section])
        apply_special(
            data, translations, empty_history(),
            {"op": "site_settings", "before": before, "after": requested},
            "issue-stale-op-1", 2, datetime.now(timezone.utc), "digest-stale",
        )
        current = current_site_settings(data)
        self.assertEqual(current["seo"]["pages"]["home"]["description"]["en"], "Updated elsewhere")
        self.assertEqual(current["analytics"]["tracking_mode"], "google")
        self.assertEqual(current["analytics"]["google_measurement_id"], "G-ABC12345")

    def test_stale_payload_null_for_unknown_page_does_not_create_null_setting(self) -> None:
        data = site_data()
        before = current_site_settings(data)
        before["seo"]["pages"]["dossier"] = None
        requested = copy.deepcopy(before)
        requested["analytics"].update({"tracking_mode": "google", "google_measurement_id": "G-ABC12345"})
        apply_special(
            data, {"schema_version": 1, "pairs": []}, empty_history(),
            {"op": "site_settings", "before": before, "after": requested},
            "issue-null-page-op-1", 4, datetime.now(timezone.utc), "digest-null-page",
        )
        stored_pages = data["settings"]["seo"]["pages"]
        self.assertNotIn("dossier", stored_pages)
        self.assertEqual(current_site_settings(data)["analytics"]["tracking_mode"], "google")

    def test_stale_site_settings_reject_same_field_conflict(self) -> None:
        data = site_data()
        before = current_site_settings(data)
        requested = copy.deepcopy(before)
        requested["seo"]["pages"]["home"]["title"]["en"] = "Admin title"
        newer = copy.deepcopy(before)
        newer["seo"]["pages"]["home"]["title"]["en"] = "Newer title"
        for section in ("general", "footer", "seo", "analytics", "contact_form", "error_page"):
            data["settings"][section] = copy.deepcopy(newer[section])
        with self.assertRaisesRegex(ValueError, r"seo\.pages\.home\.title\.en"):
            apply_special(
                data, {"schema_version": 1, "pairs": []}, empty_history(),
                {"op": "site_settings", "before": before, "after": requested},
                "issue-conflict-op-1", 3, datetime.now(timezone.utc), "digest-conflict",
            )

    def test_invalid_enabled_cloudflare_token_is_rejected(self) -> None:
        data = site_data()
        settings = current_site_settings(data)
        settings["analytics"] = {"enabled": True, "token": "not-a-token"}
        with self.assertRaises(ValueError):
            validate_site_settings(settings, data)


if __name__ == "__main__":
    unittest.main()
