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
                "DRAFT_KEY",
                "TRANSLATION_DRAFT_KEY",
                'op: "translations"',
            ),
            "admin/homepage.js": (
                "HOMEPAGE_DRAFT_KEY",
                "function homepageOperation()",
            ),
            "admin/layout.js": (
                "LAYOUT_DRAFT_KEY",
                "function layoutOperation()",
            ),
            "admin/people.js": (
                "PEOPLE_DRAFT_KEY",
                "function peopleOperation()",
            ),
            "admin/site-settings.js": (
                "DRAFT_KEY",
                "function operation()",
            ),
            "admin/notifications.js": (
                "ARXIV_SUGGESTIONS_DRAFT_KEY",
                "GENERAL_NOTIFICATIONS_DRAFT_KEY",
                "function arxivSuggestionsOperation()",
                "function notificationsOperation()",
            ),
            "admin/personal-profile.js": (
                "DRAFT_KEY",
                "function profileOperation()",
            ),
        }

        for relative, markers in contracts.items():
            source = read(relative)

            with self.subTest(file=relative):
                self.assertIn("localStorage.setItem(", source)

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

        registry = re.search(
            r"const ACTIVE_DRAFT_KEYS\s*=\s*\[(.*?)\];",
            aliases,
            re.S,
        )
        self.assertIsNotNone(registry)

        registered_keys = set(
            re.findall(r"""['"]([^'"]+)['"]""", registry.group(1))
        )

        manager_files = (
            "admin/index.html",
            "admin/homepage.js",
            "admin/layout.js",
            "admin/people.js",
            "admin/site-settings.js",
            "admin/notifications.js",
            "admin/personal-profile.js",
        )

        key_pattern = (
            r"\b[A-Z_]*(?:DRAFT_KEY|RECOVERY_KEY|"
            r"LAYOUT_LINK_KEY|STALE_TRANSLATION_KEY)"
            r"\s*=\s*['\"](hctsui-[^'\"]+)['\"]"
        )

        for relative in manager_files:
            source = read(relative)
            active_keys = re.findall(key_pattern, source)

            with self.subTest(file=relative):
                self.assertTrue(active_keys)

            for key in active_keys:
                with self.subTest(file=relative, key=key):
                    self.assertIn(key, registered_keys)

        for marker in (
            "localStorage.removeItem(key)",
            "clearHomepageDraft",
            "clearPeopleDraft",
            "clearArxivSuggestionsDraft",
            "clearGeneralNotificationsDraft",
            "clearSiteSettingsDraft",
            "clearAllCmsDrafts",
            "clearSubmittedDraft",
        ):
            self.assertIn(marker, aliases)

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
            "fieldChange(",
            "aliasDifference(",
            "chips(aliases.added,'added')",
            "chips(aliases.removed,'removed')",
            ".people-diff-chip.added",
            ".people-diff-chip.removed",
            "window.peoplePreviewHtml=detailedPeoplePreview",
            "window.peopleHistoryPreviewHtml",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, aliases)

if __name__ == "__main__":
    unittest.main()
