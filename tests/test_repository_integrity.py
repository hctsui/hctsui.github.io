from __future__ import annotations

import unittest
from pathlib import Path

from _contracts import ROOT, read


class RequiredFileTests(unittest.TestCase):
    def test_required_admin_assets_exist(self) -> None:
        for relative in (
            "admin/index.html",
            "admin/guide.html",
            "admin/homepage.js",
            "admin/homepage-v1.js",
            "admin/layout-v2.js",
            "admin/tags-v1.js",
            "admin/admin-icon.svg",
            "admin/admin-icon.png",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_required_cms_pipeline_files_exist(self) -> None:
        for relative in (
            "tools/process_batch_request.py",
            "tools/build_site.py",
            "tools/build_cv.py",
            "tools/homepage_config.py",
            "tools/render_grouped_sections.py",
            "tools/update_cv_links.py",
            "tools/validate_site.py",
            "tools/validate_translations.py",
            ".github/workflows/process-website-batch.yml",
            ".github/workflows/daily-upcoming.yml",
            ".github/workflows/deploy-cms-pages.yml",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)


class CmsOnlyIssueFlowTests(unittest.TestCase):
    def test_only_batch_issue_template_and_config_remain(self) -> None:
        folder = ROOT / ".github" / "ISSUE_TEMPLATE"
        actual = {path.name for path in folder.iterdir() if path.is_file()}
        self.assertEqual(actual, {"batch-changes.yml", "config.yml"})

    def test_batch_template_matches_admin_and_workflow(self) -> None:
        admin = read("admin/index.html")
        template = read(".github/ISSUE_TEMPLATE/batch-changes.yml")
        workflow = read(".github/workflows/process-website-batch.yml")
        self.assertIn("template=batch-changes.yml", admin)
        self.assertIn('title: "[Website: Batch] "', template)
        self.assertIn("startsWith(github.event.issue.title, '[Website: Batch]')", workflow)

    def test_legacy_form_pipeline_is_removed(self) -> None:
        for relative in (
            ".github/workflows/process-website-form.yml",
            "tools/build_dynamic_forms.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_active_workflows_do_not_regenerate_old_forms(self) -> None:
        for relative in (
            ".github/workflows/process-website-batch.yml",
            ".github/workflows/daily-upcoming.yml",
            ".github/workflows/deploy-cms-pages.yml",
        ):
            text = read(relative)
            self.assertNotIn("build_dynamic_forms.py", text, relative)
            self.assertNotIn("add-conference.yml", text, relative)
            self.assertIn("python3 -m unittest discover -s tests", text, relative)


class FilenameCleanupTests(unittest.TestCase):
    def test_unversioned_icon_is_canonical(self) -> None:
        for relative in (
            "admin/admin-icon-v13.svg",
            "admin/admin-icon-v13.png",
            "admin/admin-icon-v13-180.png",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_homepage_manager_has_unversioned_canonical_filename(self) -> None:
        self.assertTrue((ROOT / "admin/homepage.js").is_file())
        loader = read("admin/homepage-v1.js")
        self.assertIn("homepage.js", loader)
        self.assertLess(len(loader.splitlines()), 25)

    def test_high_risk_legacy_filenames_are_not_renamed_blindly(self) -> None:
        # These files are referenced throughout generated pages and the large
        # Admin shell. They remain until a dedicated all-reference migration.
        for relative in (
            "admin/layout-v2.js",
            "admin/tags-v1.js",
            "assets/script-v23.js",
            "assets/style-v23.css",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)


class ObsoleteRegressionFileTests(unittest.TestCase):
    def test_old_mixed_regression_files_are_removed(self) -> None:
        for relative in (
            "tests/test_admin_regressions.py",
            "tests/test_home_profile.py",
            "tests/test_admin_hotfix.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
