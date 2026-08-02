from __future__ import annotations

import unittest

from _contracts import node_check, read


class InlineNavigationAndIdentityContracts(unittest.TestCase):
    def test_extension_is_loaded_after_existing_admin_extensions(self) -> None:
        aliases = read("admin/people-aliases.js")
        self.assertIn("navigationSettingsInlineScript", aliases)
        self.assertIn("navigation-settings.js?v=", aliases)

    def test_inline_navigation_editor_uses_layout_draft(self) -> None:
        script = read("admin/navigation-settings.js")
        for marker in (
            "data-inline-navigation-editor",
            "layoutDraft.pages",
            "page.show_in_navigation=visible",
            "saveLayoutDraft(message)",
            "data-inline-nav-move",
            "data-inline-nav-visible",
            "直接調整導覽列",
        ):
            self.assertIn(marker, script)
        self.assertIn("const oldButton=card.querySelector(\'[data-open-page-manager]\')", script)
        self.assertIn("oldButton?.remove()", script)

    def test_identity_help_explains_desktop_and_mobile_locations(self) -> None:
        script = read("admin/navigation-settings.js")
        for marker in (
            "公開網站導覽列最左上角",
            "點擊後返回首頁",
            "手機或窄螢幕",
            "品牌名稱（英文，左上角）",
            "手機選單按鈕（中文）",
            "data-identity-placement-guide",
        ):
            self.assertIn(marker, script)

    def test_extension_javascript_parses(self) -> None:
        node_check("admin/navigation-settings.js")


if __name__ == "__main__":
    unittest.main()
