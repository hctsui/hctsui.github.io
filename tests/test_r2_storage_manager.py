from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R2StorageManagerContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (ROOT / "admin" / "r2-media.js").read_text(encoding="utf-8")
        self.loader = (ROOT / "admin" / "people-aliases.js").read_text(encoding="utf-8")
        self.config = (ROOT / "content" / "media-config.json").read_text(encoding="utf-8")

    def test_r2_manager_is_loaded(self) -> None:
        self.assertIn("r2-media.js?v=20260803-2", self.loader)
        self.assertIn("r2MediaLibraryScript", self.loader)

    def test_r2_is_a_website_settings_section(self) -> None:
        self.assertIn("data-r2-settings-section", self.script)
        self.assertIn("id=\"r2SettingsPane\"", self.script)
        self.assertIn("R2 儲存桶", self.script)
        self.assertNotIn("r2-media-launcher", self.script)

    def test_dynamic_folders_and_upload_are_supported(self) -> None:
        self.assertIn("safePrefix", self.script)
        self.assertIn("lecturenotes/algebra", self.script)
        self.assertIn("method:'PUT'", self.script)
        self.assertIn("/cms/media?key=", self.script)
        self.assertNotIn("/cms/media/import", self.script)
        self.assertNotIn("data-r2-import-legacy", self.script)

    def test_home_photo_creates_site_settings_draft(self) -> None:
        self.assertIn('data-general-field=\"cover.image\"', self.script)
        self.assertIn('data-general-field=\"cover.fallback\"', self.script)
        self.assertIn('data-seo-global=\"default_image\"', self.script)
        self.assertIn("photo-original.webp", self.script)
        self.assertIn("photo-1440.webp", self.script)

    def test_bucket_configuration(self) -> None:
        self.assertIn('"bucket_name": "hctsui-website-media"', self.config)
        self.assertIn('"public_base": "https://hctsui-website-worker.hctsui-math.workers.dev/media"', self.config)

    def test_javascript_syntax(self) -> None:
        for path in (ROOT / "admin" / "r2-media.js", ROOT / "admin" / "people-aliases.js"):
            subprocess.run(["node", "--check", str(path)], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
