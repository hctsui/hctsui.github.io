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
        items = {row["id"]: row for row in data["profile_items"]}
        for item_id in ("profile-name", "contact-affiliation", "profile-position"):
            self.assertEqual(items[item_id]["category_id"], "personal-profile")
        self.assertNotIn(
            "home-contact",
            {row["category_id"] for row in items["contact-affiliation"]["display_placements"]},
        )
        self.assertIn(
            "home-contact",
            {row["category_id"] for row in items["contact-institutional-email"]["display_placements"]},
        )

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

    def test_admin_supports_dossier_order_mixed_style_and_profile_form(self) -> None:
        layout = self.read("admin/dossier-category.js")
        profile = self.read("admin/personal-profile.js")
        for marker in (
            "dossier_category_order", "一般內容（不限風格）", "data-category-style-preview",
            "放進審查資料", "額外顯示位置", "data-placement-add-select",
            "['dossier','__dossier__',PDF_CV_PAGE_ID]", "bindDossierOrderControls",
            "['featured_publications','upcoming'].includes(category.kind)",
            "decorateRecordPageBadges", "formActions.before(details)", "VIRTUAL_PAGES", "PDF 履歷",
        ):
            self.assertIn(marker, layout)
        for marker in (
            "<strong>個人資料編輯</strong>", "choices.prepend(button)", "removeSettingsIntroHints",
            "個人資料顯示位置", "op:'personal_profile'", "data-profile-placement-select",
            "#generalSettingsPane", "data-personal-profile-general-choice", "showGeneralProfilePanel",
            "persistProfilePlacementGroup", "filter(category=>category.id!==PROFILE_CATEGORY_ID",
            "openPersonalProfileSettings", "openPdfCvOrder", "record?._layout_id===PERSONAL_PAGE_ID",
            "record?._layout_id===PDF_CV_PAGE_ID", "selector.value='__cv__'",
        ):
            self.assertIn(marker, profile)
        self.assertNotIn("這裡是個人資料的唯一來源。", profile)
        self.assertNotIn("姓名、所屬單位、職位與聯絡資訊", profile)
        self.assertNotIn("操作方式與 PDF 履歷相同", layout)
        self.assertNotIn("審查資料排序</strong><p>", layout)

    def test_people_database_uses_single_canonical_draft_flow(self) -> None:
        media = self.read("admin/media.js")
        safety_path = ROOT / "admin/people-safety.js"
        if safety_path.exists():
            safety = safety_path.read_text(encoding="utf-8")
            self.assertNotIn("重新載入正式資料", safety)
            self.assertNotIn("MutationObserver", safety)
            self.assertNotIn("shouldBlockSubmission", safety)
        self.assertNotIn("people-safety.js", media)
        self.assertNotIn("mergePeople", media)
        self.assertNotIn("PEOPLE_BACKUP_KEY", media)
        self.assertIn("canonical people.js draft flow", media)
        self.assertRegex(media, r'people-aliases\.js\?v=[^"\']+')

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
        self.assertNotIn("Legacy documentation test compatibility markers", guide)

    def test_dossier_profile_and_print_contracts(self) -> None:
        builder = self.read("tools/build_dossier.py")
        css = self.read("assets/dossier.css")
        self.assertIn('for key in ("name", "affiliation", "position")', builder)
        self.assertIn('excluded = {"name", "affiliation", "position"}', builder)
        self.assertIn("column-count: 2", css)
        self.assertIn("display: contents !important", css)
        self.assertIn("break-inside: auto", css)
        self.assertIn("module.apply_home_cover = apply_home_cover", self.read("tools/cms_extensions.py"))

    def test_batch_backend_persists_new_structures(self) -> None:
        backend = self.read("tools/run_process_batch_request.py")
        for marker in ("dossier_category_order", "display_placements", 'op.get("op") != "personal_profile"'):
            self.assertIn(marker, backend)


if __name__ == "__main__":
    unittest.main()
