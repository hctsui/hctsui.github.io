from __future__ import annotations

import re
import unittest

from _contracts import node_check, read

ADMIN_PAGE = read("admin/index.html")
MAIN = read("admin/homepage.js")
LAYOUT = read("admin/layout.js")
TAGS = read("admin/tags.js")
GUIDE = read("admin/guide.html")


class AdminLoadingContracts(unittest.TestCase):
    def test_all_admin_javascript_parses(self) -> None:
        for relative in (
            "admin/tags.js",
            "admin/layout.js",
            "admin/homepage.js",
            "admin/people.js",
            "admin/notifications.js",
            "admin/site-settings.js",
            "admin/github-submit.js",
            "admin/analytics-report.js",
        ):
            with self.subTest(relative=relative):
                node_check(relative)

    def test_admin_loads_canonical_scripts_with_cache_busting(self) -> None:
        expected = (
            "tags.js",
            "layout.js",
            "homepage.js",
            "people.js",
            "notifications.js",
            "site-settings.js",
            "github-submit.js",
            "analytics-report.js",
            "media.js",
        )
        for filename in expected:
            match = re.search(
                rf'<script src="{re.escape(filename)}\?v=[^"]+"></script>',
                ADMIN_PAGE,
            )
            self.assertIsNotNone(match, filename)
        
    def test_mobile_github_submit_keeps_manual_fallback(self) -> None:
        submit = read("admin/github-submit.js")
        for marker in (
            'id="submitBatch"',
            'id="manualSubmitBatch"',
            'id="githubLogin"',
            "/cms/auth/start",
            "/cms/submit",
            "validatePeopleDraft",
            "request_id",
            "website-form-applied",
            "/cms/status?issue=",
        ):
            self.assertIn(marker, ADMIN_PAGE + submit)
        self.assertLess(
            ADMIN_PAGE.index('src="tags.js'),
            ADMIN_PAGE.index('src="github-submit.js'),
        )

    def test_admin_has_authenticated_cloudflare_and_google_reports(self) -> None:
        settings = read("admin/site-settings.js")
        report = read("admin/analytics-report.js")
        worker = read("integrations/contact-worker.js")

        for marker in (
            'id="analyticsReportPanel"',
            "/cms/analytics?provider=",
            "data-analytics-range",
            "data-analytics-report-provider",
        ):
            self.assertIn(marker, settings + report)

        self.assertIn("requireSession(request, env)", worker)

        self.assertLess(
            ADMIN_PAGE.index('src="github-submit.js'),
            ADMIN_PAGE.index('src="analytics-report.js'),
        )


    def test_admin_disables_stale_browser_cache(self) -> None:
        for marker in (
            'http-equiv="Cache-Control"',
            'no-cache, no-store, must-revalidate',
            'http-equiv="Pragma"',
            'http-equiv="Expires"',
        ):
            self.assertIn(marker, ADMIN_PAGE)

    def test_admin_shell_is_installed_before_feature_wrappers(self) -> None:
        self.assertLess(
            MAIN.index("installAdminShellImmediately"),
            MAIN.index("const HOMEPAGE_DRAFT_KEY"),
        )

    def test_admin_icon_and_return_link_exist(self) -> None:
        self.assertIn("admin-icon.svg", MAIN)
        self.assertIn("data-return-site", MAIN)
        self.assertIn("../index.html", MAIN)
        self.assertIn('href="admin-icon.svg"', GUIDE)


class ExistingFeatureContracts(unittest.TestCase):
    def test_general_and_course_pages_have_separate_admin_flows(self) -> None:
        for marker in (
            "openPageTypeChooser",
            'data-page-type-choice="general"',
            'data-page-type-choice="course"',
            "一般頁面",
            "課程頁面",
            "data-course-schedule",
            "data-add-course-material",
            "coursePages()",
            "external_course_url",
            "外部課程網址",
        ):
            self.assertIn(marker, LAYOUT)
        self.assertIn("'general_page','course_page'", MAIN)

    def test_general_content_style_controls_exist(self) -> None:
        for marker in (
            "data-style-choice-kind=",
            "aria-pressed=",
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
            "每行一個，例如 Tsui, Hung-Chun",
            "data-person-id",
            "chooseSuggestion",
            "peopleOperation",
            "validatePeopleDraft",
        ):
            self.assertIn(marker, people)
        self.assertNotIn("datalist", people)
        self.assertIn("peopleExactCounterpart", people)
        self.assertIn("applyPersonPair", ADMIN_PAGE)
        self.assertIn('method = found.method || "人名連結"', ADMIN_PAGE)

    def test_people_loading_waits_for_remote_data_without_empty_fallback(self) -> None:
        people = read("admin/people.js")
        aliases = read("admin/people-aliases.js")
        for marker in (
            "peopleLoadPromise",
            "await peopleLoadPromise",
            "fetchPeopleRemote",
            "peopleLoadState='loading'",
            "[person.id,person.name.en",
            "系統沒有以空資料取代正式檔案",
            "mergeSavedPeople",
            "PEOPLE_RECOVERY_KEY",
            "refreshPeoplePreview",
            "siteDataReady",
            "if(!siteDataReady()||typeof effectiveSite",
            "人名連結介面初始化失敗",
        ):
            self.assertIn(marker, people)
        self.assertNotIn(".catch(()=>empty())", people)
        self.assertNotIn("location.replace", aliases)
        self.assertNotIn("for(let attempt=0;attempt<45", aliases)

    def test_publication_editor_has_optional_bibtex_field(self) -> None:
        for marker in (
            "data-bibtex-toggle",
            "data-copy-bibtex",
            "data-copy-citation",
            "data-citation-format",
            "publication-action",
            "citation-panel",
            "data-citation-close",
        ):
            self.assertIn(marker, ADMIN_PAGE + read("assets/script.js") + read("tools/build_site.py"))


class SiteSettingsContracts(unittest.TestCase):
    def test_database_and_site_settings_are_available(self) -> None:
        people = read("admin/people.js")
        settings = read("admin/site-settings.js")

        self.assertIn('data-tab="dictionary"', ADMIN_PAGE)

        for kind in ("translations", "people"):
            self.assertIn(
                f'data-database-type="{kind}"',
                people,
            )

        self.assertIn('data-tab="siteSettings"', settings)

        for section in (
            "general",
            "contactForm",
            "seo",
            "analytics",
        ):
            self.assertIn(
                f'data-site-settings-section="{section}"',
                settings,
            )

    def test_translation_preview_has_diff_controls(self) -> None:
        self.assertIn(
            'data-preview-operation="translations"',
            ADMIN_PAGE,
        )
        for marker in (
            "translation-diff-change-label",
            "querySelector",
        ):
            self.assertIn(marker, TAGS)


    def test_analytics_404_and_preview_controls_exist(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            'data-analytics-field="tracking_mode"',
            "data-error-color",
            'data-contact-panel="form"',
            'data-contact-panel="design"',
            "data-contact-page-field",
            "data-contact-color",
            "siteSettingsOperation",
        ):
            self.assertIn(marker, settings)

    def test_contact_and_404_system_pages_route_to_settings(self) -> None:
        layout = read("admin/layout.js")
        settings = read("admin/site-settings.js")
        for marker in (
            "system-page:contact",
            "system-page:404",
            "_settings_section:'contactForm'",
            "_settings_panel:'design'",
            "_settings_section:'errorPage'",
            "openSiteSettingsSection",
        ):
            self.assertIn(marker, layout)
        self.assertIn("window.openSiteSettingsSection=function(section,subsection)", settings)


    def test_site_settings_draft_is_listed_in_common_drafts(self) -> None:
        for marker in (
            "siteSettingsDraftRow",
            'data-edit-special-draft="site_settings"',
            'data-preview-special-draft="site_settings"',
            'data-drop-special-draft="site_settings"',
            "previewSpecialDraft",
        ):
            self.assertIn(marker, ADMIN_PAGE)

    def test_contact_form_has_fixed_email_subject(self) -> None:
        settings = read("admin/site-settings.js")
        builder = read("tools/build_site.py")
        worker = read("integrations/contact-worker.js")
        self.assertIn("email_subject", settings + builder)
        self.assertIn('name="visitor_subject"', builder)
        self.assertIn("EMAIL_SUBJECT", worker)

if __name__ == "__main__":
    unittest.main()
