import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "admin" / "homepage-v1.js").read_text(encoding="utf-8")
GUIDE = (ROOT / "admin" / "guide.html").read_text(encoding="utf-8")


class AdminHotfixTests(unittest.TestCase):
    def test_record_controls_resolve_latest_renderer(self) -> None:
        self.assertIn("search.oninput=()=>renderRecords()", SCRIPT)
        self.assertIn("filter.onchange=()=>renderRecords()", SCRIPT)
        self.assertIn("viewSort.onchange=()=>renderRecords()", SCRIPT)

    def test_every_order_item_has_move_control(self) -> None:
        self.assertIn("搬移（無相容類別）", SCRIPT)
        self.assertIn("搬移（PDF 檢視不可用）", SCRIPT)
        self.assertIn('data-move-item=', SCRIPT)

    def test_general_styles_are_editable_and_previewed(self) -> None:
        for label in ("標準時間軸", "雙欄紀錄", "標題清單", "資訊卡片", "標籤列表", "精簡時間軸"):
            self.assertIn(label, SCRIPT)
            self.assertIn(label, GUIDE)
        self.assertIn("decorateGeneralEditor", SCRIPT)
        self.assertIn("saveGeneralCurrent", SCRIPT)

    def test_homepage_manager_uses_targeted_refresh(self) -> None:
        self.assertIn("refreshHomepageSurfaces", SCRIPT)
        self.assertIn("變更會自動存成草稿", SCRIPT)
        self.assertNotIn("只控制首頁雙欄，不會刪除原始資料", SCRIPT)

    def test_guide_keeps_repository_required_sections(self) -> None:
        for heading in (
            "標準工作流程",
            "欄位、小標註與自動填寫",
            "排序、頁面與類別",
            "10. 還原",
            "疑難排解",
            "送出前完整檢查",
        ):
            self.assertIn(heading, GUIDE)

    def test_homepage_is_integrated_into_home_order_categories(self) -> None:
        self.assertIn("category.kind==='featured_publications'", SCRIPT)
        self.assertIn("category.kind==='upcoming'", SCRIPT)
        self.assertIn("homepageOrderCategoryCard", SCRIPT)
        self.assertIn("目前顯示順序", SCRIPT)
        self.assertIn("目前無變更", SCRIPT)
        self.assertIn("有未送出變更", SCRIPT)

    def test_activity_entry_groups_four_forms_and_has_back_button(self) -> None:
        self.assertIn("LABEL.academic_event='活動'", SCRIPT)
        self.assertIn("LABEL.organization='學術籌辦'", SCRIPT)
        for kind in ("conference", "talk", "visit", "organization"):
            self.assertIn(f"['{kind}'", SCRIPT)
        self.assertIn("返回活動類型", SCRIPT)

    def test_long_order_titles_do_not_push_move_selector_down(self) -> None:
        self.assertIn("grid-template-columns:minmax(0,1fr) max-content", SCRIPT)
        self.assertIn(".layout-order-item-actions{display:flex;flex-wrap:nowrap", SCRIPT)

    def test_activity_filter_keeps_four_independent_types(self) -> None:
        filter_types = "types=['page','category','publication','conference','talk','visit','organization','honor','teaching','general_content']"
        self.assertIn(filter_types, SCRIPT)
        for kind in ("conference", "talk", "visit", "organization"):
            self.assertIn(kind, SCRIPT)
        self.assertIn("types=['page','category','publication','academic_event','teaching','generic']", SCRIPT)
        self.assertIn("LABEL.organization='學術籌辦'", SCRIPT)

    def test_general_content_filter_is_single_combined_option(self) -> None:
        self.assertIn("LABEL.general_content='一般內容'", SCRIPT)
        self.assertIn("filter==='general_content'", SCRIPT)
        self.assertIn("GENERAL_CONTENT_FILTER_TYPES", SCRIPT)
        self.assertIn("'interest','education','generic','contact','personal'", SCRIPT)
        self.assertNotIn("types=['page','category',...TYPES]", SCRIPT)
        self.assertIn("合併成單一「一般內容」選項", GUIDE)


class CvSubtitlePatchTests(unittest.TestCase):
    def test_patcher_uses_shared_lighter_subtitle_rule(self) -> None:
        patcher = (ROOT / "apply-update.py").read_text(encoding="utf-8")
        self.assertIn(r"\newcommand{\cvgroup}[1]", patcher)
        self.assertIn(r"primaryColor!28", patcher)
        self.assertIn(r"\titlerule[0.45pt]", patcher)
        for target in (
            "Hung-Chun-Tsui-CV.template.tex",
            "Hung-Chun-Tsui-CV-zh.template.tex",
            "Hung-Chun-Tsui-CV.tex",
            "Hung-Chun-Tsui-CV-zh.tex",
        ):
            self.assertIn(target, patcher)

    def test_guide_explains_future_groups_use_same_style(self) -> None:
        for label in ("Preprints", "Journal Articles", "National Tsing Hua University"):
            self.assertIn(label, GUIDE)
        self.assertIn("較淡的右側橫線", GUIDE)

class HomepageOrderingTests(unittest.TestCase):
    def test_automatic_publications_keep_manual_relative_order(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "homepage_config", ROOT / "tools" / "homepage_config.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        data = {
            "settings": {
                "homepage": {
                    "publications": {
                        "mode": "latest",
                        "limit": 2,
                        "selected_ids": ["paper-b", "paper-a"],
                    },
                    "activities": {"mode": "manual", "limit": 1, "selected_ids": []},
                }
            },
            "publications": [
                {"id": "paper-a", "date": "2026-04-05"},
                {"id": "paper-b", "date": "2026-03-11"},
                {"id": "paper-c", "date": "2025-01-01"},
            ],
            "activities": [],
        }
        self.assertEqual(
            [item["id"] for item in module.homepage_publications(data)],
            ["paper-b", "paper-a"],
        )

    def test_new_automatic_candidate_is_appended_after_retained_order(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "homepage_config_new", ROOT / "tools" / "homepage_config.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        data = {
            "settings": {
                "homepage": {
                    "publications": {
                        "mode": "latest",
                        "limit": 2,
                        "selected_ids": ["paper-b", "paper-a"],
                    },
                    "activities": {"mode": "manual", "limit": 1, "selected_ids": []},
                }
            },
            "publications": [
                {"id": "paper-new", "date": "2026-05-01"},
                {"id": "paper-a", "date": "2026-04-05"},
                {"id": "paper-b", "date": "2026-03-11"},
            ],
            "activities": [],
        }
        self.assertEqual(
            [item["id"] for item in module.homepage_publications(data)],
            ["paper-a", "paper-new"],
        )



class AdminResetAndPreviewTests(unittest.TestCase):
    def test_all_order_sections_have_reset_controls(self) -> None:
        self.assertIn('data-reset-home-section=', SCRIPT)
        self.assertIn('data-reset-order-category=', SCRIPT)
        self.assertIn('>重設</button>', SCRIPT)
        self.assertNotIn('重設首頁設定</button>', SCRIPT)

    def test_homepage_dirty_state_compares_resolved_results(self) -> None:
        self.assertIn("resolved_ids=homepageResolvedIds", SCRIPT)
        self.assertIn("homepageComparableBundle(homepageSubmissionBundle(),data)", SCRIPT)
        self.assertIn("homepageSectionChanged(homepageBase[section]", SCRIPT)

    def test_layout_draft_is_manageable_from_drafts_tab(self) -> None:
        for marker in (
            'layout-draft-row',
            'data-edit-layout-draft',
            'data-preview-layout-draft',
            'data-drop-layout-draft',
        ):
            self.assertIn(marker, SCRIPT)
        self.assertIn('頁面／類別／排序', GUIDE)
        self.assertIn('可修改、預覽或重設', GUIDE)

    def test_page_and_category_preview_lists_real_fields(self) -> None:
        for label in (
            '導覽名稱（英文）',
            '頁面標題（中文）',
            '左上小字（英文）',
            '大標題（中文）',
            '顯示於 PDF 履歷',
            '項目位置',
        ):
            self.assertIn(label, SCRIPT)
        self.assertIn('unified-preview-card', SCRIPT)
        self.assertIn('修改前', SCRIPT)
        self.assertIn('修改後', SCRIPT)

    def test_category_help_is_compact_hint(self) -> None:
        self.assertIn('compact-layout-hint', SCRIPT)
        self.assertIn('類別是頁面中的一個大區塊；', SCRIPT)
        self.assertIn(".replace('<div class=\"notice\">類別是頁面中的一個大區塊。", SCRIPT)

    def test_clear_all_drafts_includes_layout(self) -> None:
        self.assertIn('installClearAllDraftHandler', SCRIPT)
        self.assertIn('layoutDraft=clone(layoutBase)', SCRIPT)
        self.assertIn('localStorage.removeItem(LAYOUT_DRAFT_KEY)', SCRIPT)

    def test_general_style_preview_shows_style_and_category_changes(self) -> None:
        for marker in (
            "generalStyleChangePreview",
            "previewFieldRow('顯示風格'",
            "previewFieldRow('所屬類別'",
            "修改前風格 → 修改後風格",
        ):
            target = GUIDE if marker == "修改前風格 → 修改後風格" else SCRIPT
            self.assertIn(marker, target)

    def test_style_draft_removal_restores_linked_layout_change(self) -> None:
        for marker in (
            "GENERAL_LAYOUT_LINK_KEY",
            "rememberGeneralLayoutLink",
            "reconcileGeneralLayoutLinks",
            "forgetGeneralLayoutLink",
            "layoutDraft.assignments[id]=clone(link.before)",
        ):
            self.assertIn(marker, SCRIPT)
        self.assertIn("刪除該內容草稿或把風格、類別改回原狀", GUIDE)

    def test_editor_preview_has_close_button(self) -> None:
        for marker in (
            "preview-close-button",
            "installPreviewCloseButton",
            "closeEditorPreview",
            "關閉預覽",
        ):
            self.assertIn(marker, SCRIPT)
        self.assertIn("右上角有小型「關閉」按鈕", GUIDE)


class StyleCardAndAdminIdentityTests(unittest.TestCase):
    def test_style_previews_are_clickable_buttons_and_remain_collapsible(self) -> None:
        for marker in (
            '<details class="general-style-guide" open>',
            'data-style-choice-kind=',
            'aria-pressed=',
            'general-style-current',
            "styleBlock.hidden=true",
            "styleGuide?.addEventListener('click'",
        ):
            self.assertIn(marker, SCRIPT)
        self.assertIn('六張版面縮圖本身就是顯示風格按鈕', GUIDE)
        self.assertIn('左側收合箭頭', GUIDE)

    def test_admin_icon_asset_is_valid_svg(self) -> None:
        icon = ROOT / "admin" / "admin-icon.svg"
        self.assertTrue(icon.exists())
        text = icon.read_text(encoding="utf-8")
        self.assertIn('<svg', text)
        self.assertIn('linearGradient', text)
        self.assertIn('aria-label="網站管理"', text)

    def test_apply_update_adds_site_button_and_admin_identity_idempotently(self) -> None:
        import importlib.util
        import tempfile

        spec = importlib.util.spec_from_file_location("apply_update_v9", ROOT / "apply-update.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        source = """<!doctype html><html><head><title>Admin</title><style>body{}</style></head>
<body><h1>網站批次管理</h1><div class="header-actions">
<a class="button primary" href="guide.html" target="_blank">開啟完整使用手冊</a>
</div></body></html>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.html"
            path.write_text(source, encoding="utf-8")
            self.assertEqual(module.patch_admin_index(path), "已更新")
            self.assertEqual(module.patch_admin_index(path), "已是新版")
            result = path.read_text(encoding="utf-8")
        self.assertEqual(result.count('href="admin-icon.svg"'), 1)
        self.assertEqual(result.count('data-return-site'), 1)
        self.assertEqual(result.count('class="admin-title-row"'), 1)
        self.assertIn('返回網站', result)
        self.assertIn('../index.html', result)

    def test_guide_and_management_docs_describe_navigation(self) -> None:
        manage = (ROOT / "MANAGE-WEBSITE.md").read_text(encoding="utf-8")
        for marker in ('返回網站', 'admin/admin-icon.svg', '直接點選卡片'):
            self.assertIn(marker, manage)
        self.assertIn('Admin 頁首使用專用管理圖示', GUIDE)


if __name__ == "__main__":
    unittest.main()
