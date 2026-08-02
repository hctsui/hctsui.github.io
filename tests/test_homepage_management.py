from __future__ import annotations

import unittest

from _contracts import load_module

homepage = load_module("tools/homepage_config.py", "homepage_config_contracts")


class HomepageProfileNormalizationTests(unittest.TestCase):
    def test_new_description_fields_override_defaults(self) -> None:
        profile = homepage.normalized_home_profile(
            {
                "description": {"en": "Researcher", "zh": "研究人員"},
                "description_url": "https://example.com/profile",
                "description_link_text": {
                    "en": "Researcher",
                    "zh": "研究人員",
                },
            }
        )
        self.assertEqual(profile["description"]["zh"], "研究人員")
        self.assertEqual(profile["description_url"], "https://example.com/profile")

    def test_legacy_advisor_fields_migrate_without_data_loss(self) -> None:
        profile = homepage.normalized_home_profile(
            {
                "advisor": {"en": "Legacy advisor", "zh": "舊說明"},
                "advisor_url": "https://example.com/legacy",
                "advisor_link_text": {"en": "advisor", "zh": "說明"},
            }
        )
        self.assertEqual(profile["description"]["en"], "Legacy advisor")
        self.assertEqual(profile["description"]["zh"], "舊說明")
        self.assertEqual(profile["description_url"], "https://example.com/legacy")
        self.assertEqual(profile["description_link_text"]["zh"], "說明")

    def test_internal_record_overrides_defaults(self) -> None:
        data = {
            "profile_items": [
                {
                    "id": homepage.HOME_PROFILE_ITEM_ID,
                    "profile": {
                        "kicker": {"en": "Department X", "zh": "甲系"},
                        "name_en": "A",
                        "name_zh": "乙",
                        "role": {"en": "Role", "zh": "身分"},
                        "description": {"en": "Description", "zh": "說明"},
                        "actions": [
                            {
                                "label": {"en": "Lab", "zh": "實驗室"},
                                "url": "https://example.com",
                            }
                        ],
                    },
                }
            ]
        }
        profile = homepage.homepage_profile(data)
        self.assertEqual(profile["name_en"], "A")
        self.assertEqual(profile["description"]["zh"], "說明")
        self.assertEqual(profile["actions"][0]["url"], "https://example.com")


class HomepageUrlTests(unittest.TestCase):
    def test_relative_http_https_and_mailto_are_supported(self) -> None:
        profile = homepage.normalized_home_profile(
            {
                "actions": [
                    {"label": {"en": "CV", "zh": "履歷"}, "url": "cv.html"},
                    {
                        "label": {"en": "Site", "zh": "網站"},
                        "url": "https://example.com",
                    },
                    {
                        "label": {"en": "Mail", "zh": "信箱"},
                        "url": "mailto:test@example.com",
                    },
                ]
            }
        )
        self.assertEqual(
            [item["url"] for item in profile["actions"]],
            ["cv.html", "https://example.com", "mailto:test@example.com"],
        )

    def test_unsafe_and_unknown_schemes_are_dropped(self) -> None:
        profile = homepage.normalized_home_profile(
            {
                "actions": [
                    {
                        "label": {"en": "Bad", "zh": "錯誤"},
                        "url": "javascript:alert(1)",
                    },
                    {
                        "label": {"en": "Data", "zh": "資料"},
                        "url": "data:text/html,x",
                    },
                    {
                        "label": {"en": "Protocol", "zh": "協定"},
                        "url": "ftp://example.com",
                    },
                ]
            }
        )
        self.assertEqual(profile["actions"], [])


class HomepageRenderingTests(unittest.TestCase):
    def test_renderer_outputs_description_and_preserves_existing_css_class(self) -> None:
        data = {
            "profile_items": [
                {
                    "id": homepage.HOME_PROFILE_ITEM_ID,
                    "profile": {
                        "description": {
                            "en": "Research profile",
                            "zh": "研究簡介",
                        },
                        "description_url": "",
                        "actions": [],
                    },
                }
            ]
        }
        hero = homepage.render_home_profile_hero(data, "en")
        self.assertIn('<p class="home-advisor">Research profile</p>', hero)
        self.assertNotIn("Advisor: Professor", hero)

    def test_legacy_link_text_is_rendered_safely(self) -> None:
        data = {
            "profile_items": [
                {
                    "id": homepage.HOME_PROFILE_ITEM_ID,
                    "profile": {
                        "advisor": {
                            "en": "Advisor: Professor Chieh-Yu Chang",
                            "zh": "指導教授：張介玉教授",
                        },
                        "advisor_url": "https://example.com/advisor",
                        "advisor_link_text": {
                            "en": "Chieh-Yu Chang",
                            "zh": "張介玉教授",
                        },
                    },
                }
            ]
        }
        hero = homepage.render_home_profile_hero(data, "en")
        self.assertIn('href="https://example.com/advisor"', hero)
        self.assertIn(">Chieh-Yu Chang</a>", hero)

    def test_replacement_changes_only_the_hero(self) -> None:
        old = (
            '<main><section class="home-hero" id="top">old</section>'
            '<section id="publications">keep</section>'
            '<section id="contact">keep contact</section></main>'
        )
        new = homepage.replace_home_profile_hero(
            old, homepage.render_home_profile_hero({}, "en")
        )
        self.assertNotIn(">old<", new)
        self.assertIn('<section id="publications">keep</section>', new)
        self.assertIn('<section id="contact">keep contact</section>', new)


class ExistingHomepageSelectionTests(unittest.TestCase):
    def test_latest_publications_keep_manual_relative_order(self) -> None:
        data = {
            "settings": {
                "homepage": {
                    "publications": {
                        "mode": "latest",
                        "limit": 2,
                        "selected_ids": ["b", "a"],
                    },
                    "activities": {
                        "mode": "manual",
                        "limit": 1,
                        "selected_ids": [],
                    },
                }
            },
            "publications": [
                {"id": "a", "date": "2026-04-05"},
                {"id": "b", "date": "2026-03-11"},
                {"id": "c", "date": "2025-01-01"},
            ],
            "activities": [],
        }
        self.assertEqual(
            [item["id"] for item in homepage.homepage_publications(data)],
            ["b", "a"],
        )


if __name__ == "__main__":
    unittest.main()
