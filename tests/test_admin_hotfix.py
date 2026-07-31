from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "admin" / "homepage-v1.js").read_text(encoding="utf-8")
GUIDE = (ROOT / "admin" / "guide.html").read_text(encoding="utf-8")


def test_record_controls_resolve_latest_renderer() -> None:
    assert "search.oninput=()=>renderRecords()" in SCRIPT
    assert "filter.onchange=()=>renderRecords()" in SCRIPT
    assert "viewSort.onchange=()=>renderRecords()" in SCRIPT


def test_every_order_item_has_move_control() -> None:
    assert "搬移（無相容類別）" in SCRIPT
    assert "搬移（PDF 檢視不可用）" in SCRIPT
    assert 'data-move-item=' in SCRIPT


def test_general_styles_are_editable_and_previewed() -> None:
    for label in ("標準時間軸", "雙欄紀錄", "標題清單", "資訊卡片", "標籤列表", "精簡時間軸"):
        assert label in SCRIPT
        assert label in GUIDE
    assert "decorateGeneralEditor" in SCRIPT
    assert "saveGeneralCurrent" in SCRIPT


def test_homepage_manager_uses_targeted_refresh() -> None:
    assert "refreshHomepageSurfaces" in SCRIPT
    assert "每次選擇都會立即保存為本機草稿" in SCRIPT
