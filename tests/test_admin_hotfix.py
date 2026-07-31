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
        self.assertIn("types=['page','category',...TYPES]", SCRIPT)
        for kind in ("conference", "talk", "visit", "organization"):
            self.assertIn(kind, SCRIPT)
        self.assertIn("types=['page','category','publication','academic_event','teaching','generic']", SCRIPT)
        self.assertIn("LABEL.organization='學術籌辦'", SCRIPT)


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


if __name__ == "__main__":
    unittest.main()
