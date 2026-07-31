from __future__ import annotations

import unittest

from _contracts import node_check, read

MAIN = read("admin/homepage.js")
LOADER = read("admin/homepage-v1.js")
GUIDE = read("admin/guide.html")
MANAGE = read("MANAGE-WEBSITE.md")


class AdminLoadingContracts(unittest.TestCase):
    def test_canonical_script_parses(self) -> None:
        node_check("admin/homepage.js")

    def test_historical_filename_is_only_a_compatibility_loader(self) -> None:
        self.assertIn("script.src='homepage.js'", LOADER)
        self.assertIn("data-homepage-manager", LOADER)
        self.assertNotIn("const HOMEPAGE_DRAFT_KEY", LOADER)
        self.assertNotIn("function renderHomepageManager", LOADER)

    def test_admin_shell_is_installed_before_feature_wrappers(self) -> None:
        self.assertLess(
            MAIN.index("installAdminShellImmediately"),
            MAIN.index("const HOMEPAGE_DRAFT_KEY"),
        )

    def test_icon_and_return_link_have_unversioned_assets(self) -> None:
        for marker in (
            "admin-icon.svg",
            "data-admin-favicon",
            "data-admin-shortcut-icon",
            "data-admin-touch-icon",
            "admin-icon.png",
            "admin-title-row",
            "admin-brand-icon",
            "data-return-site",
            "返回網站",
            "../index.html",
        ):
            self.assertIn(marker, MAIN)
        self.assertNotIn("admin-icon-v", MAIN)
        self.assertIn('href="admin-icon.svg"', GUIDE)


class ExistingFeatureContracts(unittest.TestCase):
    def test_general_content_styles_remain_clickable_and_collapsible(self) -> None:
        for label in (
            "標準時間軸",
            "雙欄紀錄",
            "標題清單",
            "資訊卡片",
            "標籤列表",
            "精簡時間軸",
        ):
            self.assertIn(label, MAIN)
        for marker in (
            'data-style-choice-kind=',
            'aria-pressed=',
            'general-style-current',
            '<details class="general-style-guide" open>',
            "styleGuide?.addEventListener('click'",
        ):
            self.assertIn(marker, MAIN)

    def test_ordering_moving_homepage_and_draft_controls_remain_present(self) -> None:
        for marker in (
            "data-move-item",
            "data-reset-order-category",
            "data-reset-home-section",
            "homepageOrderCategoryCard",
            "layout-draft-row",
            "installClearAllDraftHandler",
            "GENERAL_LAYOUT_LINK_KEY",
        ):
            self.assertIn(marker, MAIN)

    def test_preview_close_button_keeps_normal_button_size(self) -> None:
        self.assertIn("button.className='button preview-close-button'", MAIN)
        self.assertIn(
            ".preview-close-button{float:right;margin:0 0 8px 8px}", MAIN
        )
        self.assertNotIn(".preview-close-button{float:right;margin:0 0 8px 8px;padding:", MAIN)

    def test_mailto_support_does_not_replace_normal_url_validation(self) -> None:
        self.assertIn("homepageBaseValidateEditorObject", MAIN)
        self.assertIn(r"/^mailto:[^\s@]+@[^\s@]+$/i", MAIN)
        self.assertIn("http 或 https", MAIN)


class HomepageEditorContracts(unittest.TestCase):
    def test_homepage_is_listed_as_a_page(self) -> None:
        for marker in (
            "page:home",
            "homeProfilePageFormHtml",
            "data-add-home-action",
            "data-remove-home-action",
            "data-home-action-url",
        ):
            self.assertIn(marker, MAIN)

    def test_form_has_generic_description_labels_without_one_time_hint(self) -> None:
        self.assertIn("說明（英文）", MAIN)
        self.assertIn("說明（中文）", MAIN)
        self.assertNotIn("指導教授一行（英文）", MAIN)
        self.assertNotIn("指導教授一行（中文）", MAIN)
        self.assertNotIn("首頁只開放修改下列五行文字", MAIN)
        self.assertNotIn("home-profile-scope-hint", MAIN)

    def test_legacy_advisor_data_is_migrated(self) -> None:
        self.assertIn("raw.description||raw.advisor", MAIN)
        self.assertIn("raw.description_url||raw.advisor_url", MAIN)
        self.assertIn(
            "raw.description_link_text||raw.advisor_link_text", MAIN
        )

    def test_hidden_home_record_stays_out_of_normal_catalog(self) -> None:
        for marker in (
            "HOME_PROFILE_ITEM_ID='home-profile-settings'",
            "HOME_PROFILE_CATEGORY_ID='home-publications'",
            "replaceDraftsForId(HOME_PROFILE_ITEM_ID",
            "filter(item=>String(item?.id)!==HOME_PROFILE_ITEM_ID)",
        ):
            self.assertIn(marker, MAIN)


class DocumentationContracts(unittest.TestCase):
    def test_permanent_docs_have_no_update_package_notes(self) -> None:
        for text in (GUIDE, MANAGE):
            for obsolete in (
                "apply-update.py",
                "更新包版本檢查",
                "v12 直接",
                "v13",
                "v14",
                "指導教授一行",
            ):
                self.assertNotIn(obsolete, text)

    def test_docs_use_canonical_homepage_filename(self) -> None:
        self.assertIn("admin/homepage.js", MANAGE)
        self.assertNotIn("admin/homepage-v1.js", MANAGE)


if __name__ == "__main__":
    unittest.main()
