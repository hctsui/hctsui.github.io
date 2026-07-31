from __future__ import annotations

import re
import unittest
from pathlib import Path

from _contracts import ROOT, read

VERSIONED_FILENAME = re.compile(r"(?:^|[-_.])v\d+(?=[-_.]|$)", re.IGNORECASE)
TEXT_SUFFIXES = {".html", ".js", ".css", ".py", ".md", ".yml", ".yaml", ".json", ".tex"}
OBSOLETE_NAMES = (
    "admin/headings-v1.js",
    "admin/homepage-v1.js",
    "admin/layout-v2.js",
    "admin/tags-v1.js",
    "admin/admin-icon-v13.svg",
    "admin/admin-icon-v13.png",
    "admin/admin-icon-v13-180.png",
    "assets/script-v23.js",
    "assets/style-v23.css",
)


class RequiredFileTests(unittest.TestCase):
    def test_required_admin_and_public_assets_exist(self) -> None:
        for relative in (
            "admin/index.html",
            "admin/guide.html",
            "admin/homepage.js",
            "admin/people.js",
            "admin/arxiv-notifications.js",
            "admin/layout.js",
            "admin/tags.js",
            "admin/admin-icon.svg",
            "admin/admin-icon.png",
            "assets/script.js",
            "assets/style.css",
            "404.html",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_required_cms_pipeline_files_exist(self) -> None:
        for relative in (
            "tools/process_batch_request.py",
            "tools/build_site.py",
            "tools/build_cv.py",
            "tools/homepage_config.py",
            "tools/people_config.py",
            "tools/markup_config.py",
            "content/people.json",
            "content/arxiv-suggestions.json",
            "tools/arxiv_suggestions.py",
            "tools/check_arxiv.py",
            "tools/render_grouped_sections.py",
            "tools/update_cv_links.py",
            "tools/validate_site.py",
            "tools/validate_translations.py",
            ".github/workflows/process-website-batch.yml",
            ".github/workflows/daily-upcoming.yml",
            ".github/workflows/deploy-cms-pages.yml",
            ".github/workflows/check-arxiv.yml",
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
            ".github/workflows/check-arxiv.yml",
        ):
            text = read(relative)
            self.assertNotIn("build_dynamic_forms.py", text, relative)
            self.assertNotIn("add-conference.yml", text, relative)
            self.assertIn("python3 -m unittest discover -s tests", text, relative)


class CanonicalFilenameTests(unittest.TestCase):
    def test_no_repository_filename_contains_a_v_number_suffix(self) -> None:
        offenders = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if VERSIONED_FILENAME.search(path.name):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_obsolete_versioned_paths_are_absent(self) -> None:
        for relative in OBSOLETE_NAMES:
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_text_files_do_not_reference_obsolete_filenames(self) -> None:
        hits: list[str] = []
        old_tokens = tuple(Path(name).name for name in OBSOLETE_NAMES)
        for path in ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or "tests" in path.parts:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for token in old_tokens:
                if token in text:
                    hits.append(f"{path.relative_to(ROOT)} -> {token}")
        self.assertEqual(hits, [])

    def test_admin_shell_references_canonical_scripts(self) -> None:
        page = read("admin/index.html")
        for marker in (
            '<script src="tags.js"></script>',
            '<script src="layout.js"></script>',
            '<script src="homepage.js"></script>',
            '<script src="people.js"></script>',
            '<script src="arxiv-notifications.js"></script>',
        ):
            self.assertIn(marker, page)

    def test_public_pages_reference_canonical_assets(self) -> None:
        for relative in (
            "index.html",
            "cv.html",
            "publications.html",
            "activities.html",
            "teaching.html",
        ):
            text = read(relative)
            self.assertIn('href="assets/style.css"', text, relative)
            self.assertIn('src="assets/script.js"', text, relative)
        for relative in (
            "zh/index.html",
            "zh/cv.html",
            "zh/publications.html",
            "zh/activities.html",
            "zh/teaching.html",
        ):
            text = read(relative)
            self.assertIn('href="../assets/style.css"', text, relative)
            self.assertIn('src="../assets/script.js"', text, relative)

    def test_deploy_workflow_checks_canonical_assets(self) -> None:
        workflow = read(".github/workflows/deploy-cms-pages.yml")
        for relative in (
            "admin/homepage.js",
            "admin/people.js",
            "admin/arxiv-notifications.js",
            "admin/layout.js",
            "admin/tags.js",
            "assets/script.js",
            "assets/style.css",
            "404.html",
            "admin/admin-icon.svg",
        ):
            self.assertIn(f"test -f {relative}", workflow)



    def test_custom_404_and_cloudflare_contracts_exist(self) -> None:
        page = read("404.html")
        self.assertIn('<meta name="robots" content="noindex,nofollow">', page)
        self.assertIn('data-language="en"', page)
        self.assertIn('data-language="zh"', page)
        self.assertIn("data-switch-language", page)
        self.assertNotIn("static.cloudflareinsights.com/beacon.min.js", read("admin/index.html"))

class TestSuiteStructureTests(unittest.TestCase):
    def test_obsolete_duplicate_regression_files_are_removed(self) -> None:
        for relative in (
            "tests/test_admin_regressions.py",
            "tests/test_home_profile.py",
            "tests/test_admin_hotfix.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
