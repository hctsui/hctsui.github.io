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
            "data-inline-nav-move",
            "data-inline-nav-visible",
            "function movePage(",
            "function setPageVisibility(",
            "saveLayoutDraft(",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_identity_preview_controls_exist(self) -> None:
        script = read("admin/navigation-settings.js")

        for marker in (
            "data-identity-placement-guide",
            "data-identity-preview-brand-en",
            "data-identity-preview-brand-zh",
            "data-identity-preview-menu-en",
            "data-identity-preview-menu-zh",
            "updateIdentityPreview(event.target)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_extension_javascript_parses(self) -> None:
        node_check("admin/navigation-settings.js")


if __name__ == "__main__":
    unittest.main()
