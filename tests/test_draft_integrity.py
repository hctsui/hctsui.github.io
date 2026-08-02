from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class DraftPersistenceContracts(unittest.TestCase):
    def test_every_cms_manager_has_storage_and_an_operation(self) -> None:
        contracts = {
            "admin/index.html": (
                "hctsui-batch-v12",
                "hctsui-translations-draft-v1",
                "localStorage.setItem(DRAFT_KEY",
                "TRANSLATION_DRAFT_KEY",
                'op: "translations"',
            ),
            "admin/homepage.js": (
                "hctsui-homepage-draft-v1",
                "localStorage.setItem(HOMEPAGE_DRAFT_KEY",
                "function homepageOperation()",
            ),
            "admin/layout.js": (
                "hctsui-layout-draft-v3",
                "localStorage.setItem(LAYOUT_DRAFT_KEY",
                "function layoutOperation()",
            ),
            "admin/people.js": (
                "hctsui-people-draft",
                "localStorage.setItem(PEOPLE_DRAFT_KEY",
                "function peopleOperation()",
            ),
            "admin/site-settings.js": (
                "hctsui-site-settings-draft",
                "localStorage.setItem(DRAFT_KEY",
                "function operation()",
            ),
            "admin/notifications.js": (
                "hctsui-arxiv-suggestions-draft-v1",
                "hctsui-general-notifications-draft-v1",
                "function arxivSuggestionsOperation()",
                "function notificationsOperation()",
            ),
            "admin/personal-profile.js": (
                "hctsui-personal-profile-draft-v1",
                "localStorage.setItem(DRAFT_KEY",
                "function profileOperation()",
            ),
        }
        for relative, markers in contracts.items():
            source = read(relative)
            for marker in markers:
                with self.subTest(file=relative, marker=marker):
                    self.assertIn(marker, source)

    def test_payload_collects_all_special_operations(self) -> None:
        sources = "".join(
            read(relative)
            for relative in (
                "admin/index.html",
                "admin/homepage.js",
                "admin/layout.js",
                "admin/people.js",
                "admin/site-settings.js",
                "admin/notifications.js",
                "admin/personal-profile.js",
            )
        )
        for operation in (
            "translations",
            "homepage",
            "layout",
            "people",
            "site_settings",
            "arxiv_suggestions",
            "notifications",
            "personal_profile",
        ):
            with self.subTest(operation=operation):
                self.assertRegex(sources, rf"op\s*:\s*['\"]{re.escape(operation)}['\"]")


class ClearAllDraftContracts(unittest.TestCase):
    def test_clear_all_drafts_covers_every_active_store(self) -> None:
        aliases = read("admin/people-aliases.js")
        for key in (
            "hctsui-batch-v12",
            "hctsui-translations-draft-v1",
            "hctsui-translations-stale-v1",
            "hctsui-homepage-draft-v1",
            "hctsui-layout-draft-v3",
            "hctsui-general-layout-links-v1",
            "hctsui-people-draft",
            "hctsui-people-draft-recovery-v1",
            "hctsui-site-settings-draft",
            "hctsui-arxiv-suggestions-draft-v1",
            "hctsui-general-notifications-draft-v1",
            "hctsui-personal-profile-draft-v1",
        ):
            with self.subTest(key=key):
                self.assertIn(key, aliases)
        for clearer in (
            "clearHomepageDraft",
            "clearPeopleDraft",
            "clearArxivSuggestionsDraft",
            "clearGeneralNotificationsDraft",
            "clearSiteSettingsDraft",
        ):
            with self.subTest(clearer=clearer):
                self.assertIn(clearer, aliases)
        self.assertIn("data.clearsAllCmsDrafts", aliases)
        self.assertIn("clearSubmittedDraft", aliases)
        self.assertIn("location.reload()", aliases)

    def test_clear_all_extension_is_in_the_existing_people_alias_script(self) -> None:
        aliases = read("admin/people-aliases.js")
        media = read("admin/media.js")
        self.assertIn("installDraftPreviewExtension", aliases)
        self.assertIn("peopleAliasesScript", media)
        self.assertRegex(media, r"people-aliases\.js\?v=[^\"']+")


class PeoplePreviewContracts(unittest.TestCase):
    def test_people_preview_shows_field_and_alias_differences(self) -> None:
        aliases = read("admin/people-aliases.js")
        for marker in (
            "英文姓名",
            "中文姓名",
            "學術網頁",
            "新增別名",
            "刪除別名",
            "chips(aliases.added,'added')",
            "chips(aliases.removed,'removed')",
            ".people-diff-chip.added",
            ".people-diff-chip.removed",
            "window.peoplePreviewHtml=detailedPeoplePreview",
            "window.peopleHistoryPreviewHtml",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, aliases)


class CacheBustingContracts(unittest.TestCase):
    def test_tests_do_not_lock_date_based_script_versions(self) -> None:
        exact_version = re.compile(r"\?v=20\d{6}(?:-\d+)?")
        offenders = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            if exact_version.search(path.read_text(encoding="utf-8")):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
