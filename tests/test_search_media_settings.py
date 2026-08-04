from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.r2_build_fix import apply_static_asset_paths_safely
from tools.site_settings_config import normalized_site_settings

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class SearchMediaSettingsTests(unittest.TestCase):
    def test_public_navigation_has_search_and_404_uses_shared_header(self) -> None:
        for path in ("index.html", "zh/index.html", "publications.html", "404.html"):
            text = read(path)
            self.assertIn('class="site-header"', text, path)
            self.assertIn("data-site-search", text, path)
        self.assertNotIn("not-found-header", read("404.html"))
        self.assertIn(">English</button>", read("404.html"))

    def test_images_are_centralized(self) -> None:
        # The favicon stays in GitHub because every public page needs it.
        self.assertTrue((ROOT / "assets/images/favicon.svg").is_file())

        # Old duplicate locations must remain removed.
        for legacy in (
            "photo.jpg",
            "assets/photo-640.webp",
            "assets/photo-960.webp",
            "assets/photo-1440.webp",
            "assets/favicon.svg",
        ):
            self.assertFalse((ROOT / legacy).exists(), f"Remove legacy image path: {legacy}")

        # Cover and OG images may now live either in assets/images or in R2.
        site = json.loads(read("content/site.json"))
        settings = normalized_site_settings(site.get("settings", {}), site)
        media_config = json.loads(read("content/media-config.json"))
        public_base = str(media_config["public_base"]).rstrip("/")

        references = (
            settings["general"]["cover"]["image"],
            settings["general"]["cover"]["fallback"],
            settings["seo"]["default_image"],
        )
        for value in references:
            self.assertTrue(value, "Media reference must not be empty")
            if value.startswith(("http://", "https://")):
                self.assertTrue(
                    value.startswith(public_base + "/"),
                    f"External managed media must use the configured R2 public base: {value}",
                )
            else:
                self.assertTrue(
                    value.startswith("assets/images/"),
                    f"Local managed image must stay in assets/images: {value}",
                )
                self.assertTrue((ROOT / value).is_file(), value)

        # Regression for the real R2 bug: legacy-path migration must not rewrite
        # the tail of a complete HTTPS URL.
        original = lambda text, lang: text.replace(
            "photo.jpg",
            "../assets/images/photo.jpg" if lang == "zh" else "assets/images/photo.jpg",
        )
        r2_url = public_base + "/images/photo.jpg"
        self.assertEqual(
            apply_static_asset_paths_safely(original, r2_url, "zh"),
            r2_url,
        )

    def test_media_manifest_and_admin_picker(self) -> None:
        manifest = json.loads(read("content/media.json"))
        for group in ("images", "slides", "papers"):
            self.assertIn(group, manifest)
            self.assertIsInstance(manifest[group], list)
        media = read("admin/media.js")
        self.assertIn("slides_url", media)
        self.assertIn("pdf_url", media)
        self.assertIn("data-media-kind", read("admin/site-settings.js"))
        self.assertTrue((ROOT / "admin/r2-media.js").is_file())
        config = json.loads(read("content/media-config.json"))
        self.assertEqual(config["bucket_name"], "hctsui-website-media")
        self.assertTrue(config["public_base"].endswith("/media"))

    def test_legacy_image_paths_are_migrated(self) -> None:
        settings = normalized_site_settings({
            "general": {"cover": {"image": "assets/photo-960.webp", "fallback": "photo.jpg"}},
            "seo": {"default_image": "assets/photo-1440.webp", "pages": {"home": {"og_image": "assets/favicon.svg"}}},
            "footer": {"items": [{"id": "x", "text": {"en": "X", "zh": ""}, "icon": "other", "custom_icon": "assets/favicon.svg"}]},
        })
        self.assertEqual(settings["general"]["cover"]["image"], "assets/images/photo-960.webp")
        self.assertEqual(settings["general"]["cover"]["fallback"], "assets/images/photo.jpg")
        self.assertEqual(settings["seo"]["default_image"], "assets/images/photo-1440.webp")
        self.assertEqual(settings["seo"]["pages"]["home"]["og_image"], "assets/images/favicon.svg")
        self.assertEqual(settings["footer"]["items"][0]["custom_icon"], "assets/images/favicon.svg")

    def test_public_search_index_is_populated(self) -> None:
        index = json.loads(read("content/search-index.json"))
        self.assertTrue(any(item.get("language") == "en" for item in index["items"]))
        self.assertTrue(any(item.get("language") == "zh" for item in index["items"]))

    def test_general_settings_group_owns_footer_and_404(self) -> None:
        settings = read("admin/site-settings.js")
        self.assertIn('data-site-settings-section="general">一般設定', settings)
        self.assertIn("['footer','頁尾設定']", settings)
        self.assertIn("['error','404 頁面設計']", settings)
        self.assertNotIn('data-site-settings-section="errorPage">404 頁面', settings)

    def test_citation_trigger_and_formats(self) -> None:
        page = read("publications.html")
        self.assertIn(">Cite</button>", page)
        self.assertIn("<span>biblatex</span>", page)
        self.assertIn(r"LaTeX \bibitem", page)

    def test_people_consistency_audit_exists(self) -> None:
        people = read("admin/people.js")
        self.assertIn("人名一致性檢查", people)
        self.assertIn("data-people-audit-apply-all", people)
        self.assertIn("依人名連結修正", people)


if __name__ == "__main__":
    unittest.main()
