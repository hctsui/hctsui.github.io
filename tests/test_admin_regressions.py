import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "admin" / "homepage-v1.js").read_text(encoding="utf-8")
GUIDE = (ROOT / "admin" / "guide.html").read_text(encoding="utf-8")
MANAGE = (ROOT / "MANAGE-WEBSITE.md").read_text(encoding="utf-8")


class AdminShellRegressionTests(unittest.TestCase):
    def test_shell_bootstrap_runs_before_compatibility_code(self):
        bootstrap = SCRIPT.index("installAdminShellImmediately")
        compatibility = SCRIPT.index("const HOMEPAGE_DRAFT_KEY")
        self.assertLess(bootstrap, compatibility)

    def test_favicon_title_icon_and_return_link_are_installed(self):
        for marker in (
            "data-admin-favicon",
            "data-admin-shortcut-icon",
            "admin-icon-v13.svg?v=13",
            "admin-title-row",
            "admin-brand-icon",
            "data-return-site",
            "返回網站",
            "../index.html",
        ):
            self.assertIn(marker, SCRIPT)

    def test_shell_does_not_depend_on_external_icon_loading(self):
        self.assertIn("data:image/svg+xml;base64,", SCRIPT)
        self.assertIn("image.onerror", SCRIPT)

    def test_mailto_support_remains_present(self):
        self.assertIn("homepageBaseValidateEditorObject", SCRIPT)
        self.assertIn(r"/^mailto:[^\s@]+@[^\s@]+$/i", SCRIPT)

    def test_cv_templates_keep_visible_group_rule(self):
        marker = r"\leaders\hrule height 0.45pt depth 0pt\hfill\kern0pt"
        for name in (
            "Hung-Chun-Tsui-CV.template.tex",
            "Hung-Chun-Tsui-CV-zh.template.tex",
        ):
            self.assertIn(marker, (ROOT / "cv" / name).read_text(encoding="utf-8"))

    def test_documents_no_longer_describe_update_packages(self):
        for text in (GUIDE, MANAGE):
            self.assertNotIn("apply-update.py", text)
            self.assertNotIn("v12 直接", text)
            self.assertNotIn("更新包版本檢查", text)


if __name__ == "__main__":
    unittest.main()
