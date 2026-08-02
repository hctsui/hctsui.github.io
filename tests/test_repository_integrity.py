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
            "admin/index.html", "admin/guide.html", "admin/homepage.js", "admin/people.js",
            "admin/notifications.js", "admin/media.js", "content/media.json",
            "content/search-index.json", "admin/layout.js", "admin/tags.js",
            "admin/admin-icon.svg", "admin/admin-icon.png", "assets/script.js",
            "assets/style.css", "assets/images/photo.jpg", "assets/images/favicon.svg",
            "tools/build_media_manifest.py", "tools/build_search_index.py", "contact.html",
            "zh/contact.html", "404.html",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_required_cms_pipeline_files_exist(self) -> None:
        for relative in (
            "tools/process_batch_request.py", "tools/build_site.py", "tools/build_cv.py",
            "tools/homepage_config.py", "tools/people_config.py", "tools/markup_config.py",
            "content/people.json", "content/arxiv-suggestions.json", "tools/arxiv_suggestions.py",
            "tools/check_arxiv.py", "tools/render_grouped_sections.py", "tools/update_cv_links.py",
            "tools/validate_site.py", "tools/validate_translations.py",
            ".github/workflows/process-website-batch.yml", ".github/workflows/daily-upcoming.yml",
            ".github/workflows/deploy-cms-pages.yml", ".github/workflows/check-arxiv.yml",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)


class CmsOnlyIssueFlowTests(unittest.TestCase):
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
            ".github/workflows/workflows/deploy-cms-pages.yml",
            "tools/build_dynamic_forms.py",
            "admin/people-safety.js",
            "tools/__pycache__/homepage_config.cpython-313.pyc",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_generated_files_are_ignored(self) -> None:
        ignore = read(".gitignore")
        for marker in ("__pycache__/", "*.py[cod]", "_site/", ".DS_Store"):
            self.assertIn(marker, ignore)

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

    def test_daily_build_uses_the_complete_extension_pipeline(self) -> None:
        workflow = read(".github/workflows/daily-upcoming.yml")
        for marker in (
            "python3 tools/run_with_extensions.py tools/build_site.py",
            "python3 tools/build_dossier.py", "python3 tools/inject_prefetch.py",
            "python3 tools/inject_profile_assets.py",
            "python3 tools/run_with_extensions.py tools/build_cv.py",
            "python3 tools/run_validate_site.py", "content/media.json content/search-index.json",
        ):
            self.assertIn(marker, workflow)

    def test_action_created_cms_updates_explicitly_dispatch_deployment(self) -> None:
        for relative in (
            ".github/workflows/process-website-batch.yml",
            ".github/workflows/daily-upcoming.yml",
        ):
            workflow = read(relative)
            self.assertIn("git push origin HEAD:cms", workflow)
            self.assertIn("actions: write", workflow)
            self.assertIn("gh workflow run deploy-cms-pages.yml --ref cms", workflow)
            self.assertNotIn("uses: ./.github/workflows/deploy-cms-pages.yml", workflow)


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
        expected = (
            "tags.js", "layout.js", "homepage.js", "people.js", "notifications.js", "media.js",
        )
        positions = []
        for filename in expected:
            match = re.search(
                rf'<script src="{re.escape(filename)}\?v=[^"]+"></script>',
                page,
            )
            self.assertIsNotNone(match, filename)
            positions.append(match.start())
        self.assertEqual(positions, sorted(positions))

    def test_public_pages_reference_canonical_assets(self) -> None:
        for relative in (
            "index.html", "cv.html", "publications.html", "activities.html", "teaching.html", "contact.html",
        ):
            text = read(relative)
            self.assertIn('href="assets/style.css"', text, relative)
            self.assertIn('src="assets/script.js"', text, relative)
        for relative in (
            "zh/index.html", "zh/cv.html", "zh/publications.html", "zh/activities.html",
            "zh/teaching.html", "zh/contact.html",
        ):
            text = read(relative)
            self.assertIn('href="../assets/style.css"', text, relative)
            self.assertIn('src="../assets/script.js"', text, relative)

    def test_deploy_workflow_checks_canonical_assets(self) -> None:
        workflow = read(".github/workflows/deploy-cms-pages.yml")
        for relative in (
            "admin/homepage.js", "admin/people.js", "admin/notifications.js", "admin/media.js",
            "content/media.json", "content/search-index.json", "admin/layout.js", "admin/tags.js",
            "assets/script.js", "assets/style.css", "assets/images/photo.jpg",
            "assets/images/favicon.svg", "tools/build_media_manifest.py", "tools/build_search_index.py",
            "contact.html", "zh/contact.html", "404.html", "robots.txt", "sitemap.xml",
            "admin/admin-icon.svg",
        ):
            self.assertIn(f"test -f {relative}", workflow)

    def test_private_pages_are_excluded_from_search_indexing(self) -> None:
        robots = read("robots.txt")
        sitemap = read("sitemap.xml")
        for path in ("/admin/", "/dossier.html", "/zh/dossier.html", "/content/"):
            self.assertIn(f"Disallow: {path}", robots)
        for relative in ("admin/index.html", "admin/guide.html", "dossier.html", "zh/dossier.html", "404.html"):
            self.assertIn('name="robots" content="noindex,nofollow"', read(relative), relative)
        for excluded in ("/admin/", "/dossier.html", "/zh/dossier.html", "/content/"):
            self.assertNotIn(excluded, sitemap)
        workflow = read(".github/workflows/deploy-cms-pages.yml")
        self.assertIn("404.html robots.txt sitemap.xml _site/", workflow)

    def test_google_verification_file_is_published_at_site_root(self) -> None:
        verification_files = list(ROOT.glob("google*.html"))
        self.assertTrue(verification_files, "Google verification HTML file is missing")
        workflow = read(".github/workflows/deploy-cms-pages.yml")
        self.assertIn("cp google*.html _site/", workflow)

    def test_contact_system_pages_have_canonical_contracts(self) -> None:
        for relative, asset_prefix in (("contact.html", ""), ("zh/contact.html", "../")):
            page = read(relative)
            self.assertIn('data-page="contact"', page)
            self.assertIn('class="contact-page-hero"', page)
            self.assertIn('class="contact-page-section"', page)
            self.assertIn(f'href="{asset_prefix}assets/style.css"', page)
            self.assertIn(f'src="{asset_prefix}assets/script.js"', page)
            self.assertIn('data-size="flexible"', page)
        style = read("assets/style.css")
        self.assertIn(".contact-form label,.contact-form-grid>*{min-width:0}", style)
        self.assertIn(".cf-turnstile{width:100%;max-width:100%", style)
        self.assertIn("@media(max-width:360px)", style)

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
            "tests/test_admin_regressions.py", "tests/test_home_profile.py", "tests/test_admin_hotfix.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
