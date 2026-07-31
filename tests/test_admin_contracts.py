from __future__ import annotations

import unittest

from _contracts import node_check, read

ADMIN_PAGE = read("admin/index.html")
MAIN = read("admin/homepage.js")
LAYOUT = read("admin/layout.js")
TAGS = read("admin/tags.js")
GUIDE = read("admin/guide.html")
MANAGE = read("MANAGE-WEBSITE.md")


class AdminLoadingContracts(unittest.TestCase):
    def test_all_admin_javascript_parses(self) -> None:
        for relative in (
            "admin/tags.js",
            "admin/layout.js",
            "admin/homepage.js",
            "admin/people.js",
            "admin/site-settings.js",
        ):
            with self.subTest(relative=relative):
                node_check(relative)

    def test_admin_loads_only_canonical_unversioned_scripts(self) -> None:
        expected = (
            '<script src="tags.js"></script>',
            '<script src="layout.js"></script>',
            '<script src="homepage.js"></script>',
            '<script src="people.js"></script>',
            '<script src="site-settings.js"></script>',
        )
        positions = [ADMIN_PAGE.index(marker) for marker in expected]
        self.assertEqual(positions, sorted(positions))
        for marker in expected:
            self.assertIn(marker, ADMIN_PAGE)
        for obsolete in (
            "tags-v1.js",
            "layout-v2.js",
            "homepage-v1.js",
            "headings-v1.js",
        ):
            self.assertNotIn(obsolete, ADMIN_PAGE)

    def test_admin_shell_is_installed_before_feature_wrappers(self) -> None:
        self.assertLess(
            MAIN.index("installAdminShellImmediately"),
            MAIN.index("const HOMEPAGE_DRAFT_KEY"),
        )

    def test_icon_and_return_link_use_unversioned_assets(self) -> None:
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
            "data-style-choice-kind=",
            "aria-pressed=",
            "general-style-current",
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

    def test_layout_manager_and_dictionary_extensions_remain_loaded(self) -> None:
        for marker in (
            'id="layoutManagerPage"',
            'id="generalContentFormat"',
            "layoutManagerPageId=event.target.value",
        ):
            self.assertIn(marker, LAYOUT)
        for marker in (
            "translationImportPanel",
            "toggleTagManager",
            "dictionarySearch",
        ):
            self.assertIn(marker, ADMIN_PAGE + TAGS)

    def test_preview_close_button_keeps_normal_button_size(self) -> None:
        self.assertIn("button.className='button preview-close-button'", MAIN)
        self.assertIn(
            ".preview-close-button{float:right;margin:0 0 8px 8px}", MAIN
        )
        self.assertNotIn(
            ".preview-close-button{float:right;margin:0 0 8px 8px;padding:", MAIN
        )

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


class PeopleAndBibtexContracts(unittest.TestCase):
    def test_shared_author_manager_uses_click_only_suggestions(self) -> None:
        people = read("admin/people.js")
        for marker in (
            "人名連結",
            "可能的人名（點選後才會填入）",
            "資料庫分成中英對照與人名連結",
            "每行一個，例如 Tsui, Hung-Chun",
            "data-person-id",
            "chooseSuggestion",
            "peopleOperation",
            "validatePeopleDraft",
        ):
            self.assertIn(marker, people)
        self.assertNotIn("datalist", people)

    def test_publication_editor_has_optional_bibtex_field(self) -> None:
        for marker in (
            "BibTeX（選填；留白時自動產生）",
            "data-bibtex-toggle",
            "data-copy-bibtex",
        ):
            self.assertIn(marker, ADMIN_PAGE + read("assets/script.js") + read("tools/build_site.py"))


class SiteSettingsContracts(unittest.TestCase):
    def test_database_and_site_settings_are_grouped_in_admin(self) -> None:
        people = read("admin/people.js")
        settings = read("admin/site-settings.js")
        self.assertIn('data-tab="dictionary">資料庫', ADMIN_PAGE)
        self.assertIn('data-database-type="translations">中英對照', people)
        self.assertIn('data-database-type="people">人名連結', people)
        self.assertIn('data-tab="siteSettings">網站設定', settings)
        self.assertIn('data-site-settings-section="seo">SEO／OG', settings)
        self.assertIn('data-site-settings-section="footer">頁尾', settings)

    def test_footer_editor_supports_icon_link_and_alignment(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            "小圖標",
            "超連結（選填）",
            "靠左",
            "置中",
            "靠右",
            "data-footer-move",
            "siteSettingsOperation",
        ):
            self.assertIn(marker, settings)

    def test_seo_editor_exposes_page_specific_meta_and_og_fields(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            "SEO 標題（英文）",
            "Meta description（中文）",
            "OG 標題（英文，留白沿用 SEO）",
            "本頁 OG 圖片（留白沿用預設）",
        ):
            self.assertIn(marker, settings)


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

    def test_docs_use_canonical_admin_filenames(self) -> None:
        for marker in (
            "admin/homepage.js",
            "admin/layout.js",
        ):
            self.assertIn(marker, MANAGE)
        for obsolete in (
            "admin/homepage-v1.js",
            "admin/layout-v2.js",
            "admin/tags-v1.js",
            "assets/script-v23.js",
            "assets/style-v23.css",
        ):
            self.assertNotIn(obsolete, MANAGE + GUIDE)


if __name__ == "__main__":
    unittest.main()
