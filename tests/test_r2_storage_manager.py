from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R2StorageManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (ROOT / "admin" / "r2-media.js").read_text(encoding="utf-8")
        self.loader = (ROOT / "admin" / "people-aliases.js").read_text(encoding="utf-8")

    def test_r2_loader_is_registered(self) -> None:
        self.assertIn("r2MediaLibraryScript", self.loader)
        self.assertIn("r2-media.js", self.loader)

    def test_r2_mount_controls_exist(self) -> None:
        for marker in (
            "function topLevelSettingsTabs(",
            "function cleanupR2Mounts(",
            "data-r2-settings-section",
            "r2SettingsPane",
            "data-r2-home-photo",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.script)

    def test_javascript_syntax(self) -> None:
        for relative in ("admin/r2-media.js", "admin/people-aliases.js"):
            subprocess.run(
                ["node", "--check", str(ROOT / relative)],
                check=True,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
