from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R2StorageManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = (ROOT / "admin" / "r2-media.js").read_text(encoding="utf-8")
        self.loader = (ROOT / "admin" / "people-aliases.js").read_text(encoding="utf-8")

    def test_loader_uses_non_date_cache_version(self) -> None:
        self.assertRegex(self.loader, r"r2-media\.js\?v=[^\"']+")
        self.assertIsNone(re.search(r"r2-media\.js\?v=20\d{6}(?:-\d+)?", self.loader))

    def test_r2_mount_is_unique_and_media_fields_are_scoped(self) -> None:
        self.assertIn("topLevelSettingsTabs", self.script)
        self.assertIn("cleanupR2Mounts", self.script)
        self.assertIn("node.remove()", self.script)
        self.assertNotIn("panel?.querySelector('.site-settings-tabs')", self.script)
        self.assertNotRegex(self.script, r"match\(/\(\[a-z\].*\)_url/\)")

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
