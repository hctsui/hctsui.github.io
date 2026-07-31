import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "homepage_config.py"
spec = importlib.util.spec_from_file_location("homepage_config_v14", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class HomepageProfileTests(unittest.TestCase):
    def test_defaults_match_current_homepage(self):
        profile = module.default_home_profile()
        self.assertEqual(
            profile["kicker"]["en"],
            "Department of Mathematics · National Tsing Hua University",
        )
        self.assertEqual(profile["name_en"], "Hung-Chun Tsui")
        self.assertEqual(profile["name_zh"], "崔鴻竣")
        self.assertEqual(profile["role"]["en"], "PhD student in mathematics")
        self.assertEqual(
            profile["advisor"]["en"],
            "Advisor: Professor Chieh-Yu Chang",
        )

    def test_internal_record_overrides_defaults(self):
        data = {
            "profile_items": [
                {
                    "id": module.HOME_PROFILE_ITEM_ID,
                    "profile": {
                        "kicker": {"en": "Department X", "zh": "甲系"},
                        "name_en": "A",
                        "name_zh": "乙",
                        "role": {"en": "Role", "zh": "身分"},
                        "advisor": {"en": "Advisor", "zh": "指導"},
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
        profile = module.homepage_profile(data)
        self.assertEqual(profile["name_en"], "A")
        self.assertEqual(profile["actions"][0]["url"], "https://example.com")

    def test_unsafe_button_urls_are_dropped(self):
        profile = module.normalized_home_profile(
            {
                "actions": [
                    {
                        "label": {"en": "Bad", "zh": "錯誤"},
                        "url": "javascript:alert(1)",
                    },
                    {
                        "label": {"en": "CV", "zh": "履歷"},
                        "url": "cv.html",
                    },
                ]
            }
        )
        self.assertEqual([x["url"] for x in profile["actions"]], ["cv.html"])

    def test_renderer_replaces_only_home_hero(self):
        data = {"profile_items": []}
        old = '<main><section class="home-hero" id="top">old</section><section id="other">keep</section></main>'
        new = module.replace_home_profile_hero(
            old, module.render_home_profile_hero(data, "en")
        )
        self.assertIn("Department of Mathematics", new)
        self.assertIn('<section id="other">keep</section>', new)
        self.assertNotIn(">old<", new)

    def test_rendered_actions_support_relative_external_and_mailto(self):
        hero = module.render_home_profile_hero({"profile_items": []}, "en")
        self.assertIn('href="cv.html"', hero)
        self.assertIn('href="https://orcid.org/', hero)
        self.assertIn('href="mailto:hctsui@gapp.nthu.edu.tw"', hero)


if __name__ == "__main__":
    unittest.main()
