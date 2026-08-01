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
            "admin/notifications.js",
            "admin/site-settings.js",
            "admin/github-submit.js",
            "admin/analytics-report.js",
        ):
            with self.subTest(relative=relative):
                node_check(relative)

    def test_admin_loads_canonical_scripts_with_cache_busting(self) -> None:
        expected = (
            '<script src="tags.js?v=20260801-1"></script>',
            '<script src="layout.js?v=20260801-2"></script>',
            '<script src="homepage.js?v=20260801-1"></script>',
            '<script src="people.js?v=20260802-3"></script>',
            '<script src="notifications.js?v=20260801-1"></script>',
            '<script src="site-settings.js?v=20260802-1"></script>',
            '<script src="github-submit.js?v=20260802-2"></script>',
            '<script src="analytics-report.js?v=20260802-1"></script>',
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

    def test_mobile_github_submit_keeps_manual_fallback(self) -> None:
        submit = read("admin/github-submit.js")
        for marker in (
            'id="submitBatch">直接送出修改',
            'id="manualSubmitBatch">改用 GitHub Issue 手動送出',
            'id="githubLogin">登入 GitHub',
            "hctsui-github-submit-session-v1",
            "/cms/auth/start",
            "/cms/submit",
            "validatePeopleDraft",
            "request_id",
            "website-form-applied",
            "STATUS_POLL_MS=5000",
            "/cms/status?issue=",
            "查看錯誤日誌",
            "setTimeout(()=>clearSubmittedDraft(),700)",
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
            "Cloudflare Web Analytics",
            "Google Analytics 4",
            "hctsui-github-submit-session-v1",
            "/cms/analytics?provider=",
            "data-analytics-range",
            "熱門頁面",
            "流量來源",
            "國家／地區",
            "裝置",
            "瀏覽器",
            "Worker 尚未更新到流量報表版本",
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
            "BibTeX（選填；留白時自動產生）",
            r"LaTeX \\bibitem（選填；留白時自動產生）",
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
    def test_database_and_site_settings_are_grouped_in_admin(self) -> None:
        people = read("admin/people.js")
        settings = read("admin/site-settings.js")
        self.assertIn('data-tab="dictionary">資料庫', ADMIN_PAGE)
        self.assertIn('data-database-type="translations">中英對照', people)
        self.assertIn('data-database-type="people">人名連結', people)
        self.assertIn('data-tab="siteSettings">網站設定', settings)
        order = [
            settings.index('data-site-settings-section="general">一般設定'),
            settings.index('data-site-settings-section="contactForm">聯絡表單'),
            settings.index('data-site-settings-section="seo">SEO／OG'),
            settings.index('data-site-settings-section="analytics">流量統計'),
        ]
        self.assertEqual(order, sorted(order))
        self.assertIn("site-settings-nav-shell,.database-type-shell", settings)
        self.assertIn("margin-top:20px", settings)

    def test_footer_editor_supports_icon_link_alignment_and_custom_paths(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            "小圖標",
            "版權",
            "連結",
            "地點",
            "書籍",
            "日曆",
            "其他圖標檔案路徑",
            "assets/images/my-icon.svg",
            "超連結（選填）",
            "靠左",
            "置中",
            "靠右",
            "English footer",
            "中文頁尾",
            "data-footer-move",
            "siteSettingsOperation",
        ):
            self.assertIn(marker, settings)


    def test_analytics_404_and_semantic_preview_are_editable(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            "Cloudflare Web Analytics",
            "Cloudflare Site Token",
            "Google Analytics 4",
            "Google Analytics Measurement ID",
            "開啟 Cloudflare 儀表板",
            "開啟 Google Analytics 儀表板",
            "自動返回首頁",
            "幾秒後返回首頁",
            "恢復預設顏色",
            "data-error-color",
            "網站設定：${total} 項實際變更",
            'data-contact-panel="form"',
            'data-contact-panel="design"',
            "['cover','封面照片編輯']",
            "['navigation','導覽列調整']",
            "['footer','頁尾設定']",
            "['error','404 頁面設計']",
            "data-contact-page-field",
            "data-contact-color",
        ):
            self.assertIn(marker, settings)
        self.assertIn("const equal=(a,b)=>JSON.stringify(stable(a))===JSON.stringify(stable(b))", settings)
        self.assertNotIn("draft=normalize(draft,siteDataCache)", settings)
        self.assertNotIn("網站設定尚未修改。", settings)
        for removed_hint in (
            "網站設定依序管理頁尾、聯絡表單、搜尋與分享資訊、流量統計及錯誤頁面。",
            "改回原值後會自動清除修改狀態；右側預覽會逐欄列出真正改了什麼。",
            "順序為：版權、連結、地點、書籍、日曆、其他。",
            "表單顯示在首頁聯絡區。",
            "可選 Cloudflare Web Analytics 或 Google Analytics 4",
            "GitHub Pages 找不到網址時會顯示這個雙語頁面。",
        ):
            self.assertNotIn(removed_hint, settings)

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

    def test_seo_editor_exposes_page_specific_meta_and_og_fields(self) -> None:
        settings = read("admin/site-settings.js")
        for marker in (
            "SEO 標題（英文）",
            "Meta description（中文）",
            "OG 標題（英文，留白沿用 SEO）",
            "本頁 OG 圖片（留白沿用預設）",
        ):
            self.assertIn(marker, settings)


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
        self.assertIn("通知信固定主旨", settings)
        self.assertIn("email_subject", settings + builder)
        self.assertIn('name="visitor_subject"', builder)
        self.assertIn("EMAIL_SUBJECT", worker)
        self.assertIn("Visitor subject", worker)

    def test_notification_star_control_is_explicit(self) -> None:
        notifications = read("admin/notifications.js")
        self.assertIn("☆ 加星號", notifications)
        self.assertIn("★ 已加星號", notifications)
        self.assertIn("notification-star-button", notifications)

    def test_publication_action_uses_explicit_bold_font_properties(self) -> None:
        css = read("assets/style.css")
        block = css[css.index(".pub-links > .publication-action{"):css.index(".pub-links > .publication-action:hover")]
        self.assertIn("font-family:inherit", block)
        self.assertIn("font-weight:800", block)
        self.assertNotIn("font:800 1rem/1 inherit", block)


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

    def test_docs_do_not_reference_obsolete_versioned_filenames(self) -> None:
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
