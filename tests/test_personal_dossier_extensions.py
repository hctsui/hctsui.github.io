from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cms_extensions as extensions


class PersonalProfileExtensionTests(unittest.TestCase):
    def sample_data(self) -> dict:
        return {
            "settings": {
                "categories": [
                    {
                        "id": "home-contact", "page_id": "home", "kind": "contact",
                        "label": {"en": "Contact", "zh": "聯絡"},
                        "title": {"en": "Contact", "zh": "聯絡"},
                        "intro": {"en": "", "zh": ""}, "order": 0,
                        "show_on_web": True, "show_on_cv": False,
                    },
                    {
                        "id": "cv-personal", "page_id": "cv", "kind": "personal",
                        "label": {"en": "Details", "zh": "資料"},
                        "title": {"en": "Personal Information", "zh": "個人資料"},
                        "intro": {"en": "", "zh": ""}, "order": 0,
                        "show_on_web": False, "show_on_cv": True,
                    },
                ],
                "cv_category_order": ["cv-personal"],
            },
            "profile_items": [
                {
                    "id": "contact-affiliation", "type": "contact",
                    "category_id": "home-contact", "order": 2,
                    "title": {"en": "Affiliation", "zh": "所屬單位"},
                    "description": {"en": "Old University", "zh": "舊大學"},
                },
                {
                    "id": "contact-institutional-email", "type": "contact",
                    "category_id": "home-contact", "order": 0,
                    "title": {"en": "Email", "zh": "信箱"},
                    "description": {"en": "old@example.edu", "zh": "old@example.edu"},
                },
            ],
        }

    def test_profile_sync_uses_one_primary_category_and_references(self) -> None:
        data = self.sample_data()
        extensions.sync_personal_profile(
            data,
            {
                "name": {"en": "Example Name", "zh": "範例姓名"},
                "affiliation": {"en": "Example University", "zh": "範例大學"},
                "position": {"en": "Researcher", "zh": "研究員"},
                "institutional_email": "name@example.edu", "personal_email": "",
                "website": "https://example.edu", "orcid": "",
                "address": {"en": "", "zh": ""},
                "office": {"en": "Office 1", "zh": "辦公室 1"},
                "languages": {"en": "English", "zh": "英文"},
            },
        )
        categories = {row["id"]: row for row in data["settings"]["categories"]}
        self.assertEqual(categories["personal-profile"]["kind"], "mixed")
        self.assertEqual(categories["personal-profile"]["page_id"], "personal-profile")
        self.assertEqual(categories["cv-personal"]["page_id"], "pdf-cv")
        self.assertIn("cv-personal", data["settings"]["cv_category_order"])
        # IDs are editable; managed profile records are identified by their
        # stable personal_key, not by the obsolete names used before migration.
        items = {row["personal_key"]: row for row in data["profile_items"] if row.get("personal_key")}
        for key in ("name", "affiliation", "position"):
            self.assertEqual(items[key]["category_id"], "personal-profile")
        self.assertNotIn(
            "home-contact",
            {row["category_id"] for row in items["affiliation"]["display_placements"]},
        )
        self.assertIn(
            "home-contact",
            {row["category_id"] for row in items["institutional_email"]["display_placements"]},
        )
        self.assertEqual(len(data["profile_items"]), len({row["id"] for row in data["profile_items"]}))
        self.assertEqual(len(items), len(data["profile_items"]), "profile sync must not produce duplicate managed items")

    def test_normalize_placements_removes_primary_and_duplicates(self) -> None:
        rows = extensions.normalize_placements(
            [
                {"category_id": "primary", "order": 0},
                {"category_id": "other", "order": 3},
                {"category_id": "other", "order": 9},
            ],
            primary="primary", known={"primary", "other"},
        )
        self.assertEqual(rows, [{"category_id": "other", "order": 3}])


class SourceContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_dossier_and_profile_editor_controls_exist(self) -> None:
        layout = self.read("admin/dossier-category.js")
        profile = self.read("admin/personal-profile.js")

        for marker in (
            "dossier_category_order",
            "data-category-style-preview",
            "data-placement-add-select",
            "bindDossierOrderControls",
            "VIRTUAL_PAGES",
        ):
            self.assertIn(marker, layout)

        for marker in (
            "op:'personal_profile'",
            "data-profile-placement-select",
            "openPersonalProfileSettings",
            "openPdfCvOrder",
            "persistProfilePlacementGroup",
        ):
            self.assertIn(marker, profile)

    def test_people_database_uses_single_canonical_draft_flow(self) -> None:
        media = self.read("admin/media.js")

        self.assertNotIn("people-safety.js", media)
        self.assertNotIn("mergePeople", media)
        self.assertNotIn("PEOPLE_BACKUP_KEY", media)
        self.assertRegex(
            media,
            r'people-aliases\.js\?v=[^"\']+',
        )


    def test_people_aliases_and_manual_navigation_integrity(self) -> None:
        aliases = self.read("admin/people-aliases.js")
        guide = self.read("admin/guide.html")
        for marker in (
            "chineseRomanizationAliases", "foreignNameAliases", "givenParts.join('-')",
            "dotted(letters)", "data-person-field=\"aliases\"", "window.peopleAutomaticAliases",
        ):
            self.assertIn(marker, aliases)
        ids = re.findall(r'\bid="([^"]+)"', guide)
        toc_targets = re.findall(r'<a href="#([^"]+)"', guide)
        self.assertEqual(len(ids), len(set(ids)), "manual IDs must be unique")
        self.assertFalse(set(toc_targets) - set(ids), "every manual TOC link needs a target")

    def test_dossier_builder_extension_is_registered(self) -> None:
        extensions = self.read("tools/cms_extensions.py")
        self.assertIn(
            "module.apply_home_cover = apply_home_cover",
            extensions,
        )

    def test_batch_backend_persists_new_structures(self) -> None:
        backend = self.read("tools/run_process_batch_request.py")
        for marker in ("dossier_category_order", "display_placements", 'op.get("op") != "personal_profile"'):
            self.assertIn(marker, backend)


if __name__ == "__main__":
    unittest.main()
