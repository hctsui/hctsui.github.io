"""Boundary dates for the daily homepage and Activities build."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_site import render_activity  # noqa: E402
from homepage_config import homepage_activities  # noqa: E402
from r2_build_fix import filter_upcoming_from_activities  # noqa: E402


class ActivityScheduleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items = [
            {"id": kind, "type": kind, "start_date": "2027-01-11", "end_date": "2027-01-14",
             "title": {"en": kind, "zh": kind}}
            for kind in ("organization", "talk", "visit", "conference")
        ]
        self.data = {"activities": self.items, "settings": {"homepage": {
            "activities": {"mode": "soonest", "limit": 5, "selected_ids": []},
        }}}
        self.builder = SimpleNamespace(homepage_activities=homepage_activities)

    def visible_ids(self, today: date) -> set[str]:
        category = {"page_id": "activities", "kind": "conference"}
        return {item["id"] for item in filter_upcoming_from_activities(
            self.builder, self.data, category, today, self.items
        )}

    def test_daily_boundaries_for_home_and_activities(self) -> None:
        before = date(2027, 1, 8)
        two_days_before = date(2027, 1, 9)
        starts = date(2027, 1, 11)
        ends = date(2027, 1, 14)
        finished = date(2027, 1, 15)
        for today in (before, two_days_before, starts, ends, finished):
            with self.subTest(today=today):
                upcoming = {item["id"] for item in homepage_activities(self.data, today)}
                self.assertNotIn("organization", upcoming)
                self.assertNotIn("talk", upcoming)
                self.assertEqual("visit" in upcoming, today < starts)
                self.assertEqual("organization" in self.visible_ids(today), today >= starts)
                self.assertEqual("talk" in self.visible_ids(today), today >= two_days_before)
                self.assertEqual("visit" in self.visible_ids(today), today >= starts)

        self.data["settings"]["homepage"]["activities"] = {
            "mode": "manual", "limit": 5,
            "selected_ids": ["organization", "talk", "visit", "conference"],
        }
        self.assertEqual(
            [item["id"] for item in homepage_activities(self.data, before)],
            ["visit", "conference"],
        )

    def test_visit_badge_is_localized_and_expires_after_end_date(self) -> None:
        visit = self.items[2]
        for today in (date(2027, 1, 11), date(2027, 1, 14)):
            self.assertIn('<span class="role-note">Current</span>', render_activity(visit, "en", today))
            self.assertIn('<span class="role-note">進行中</span>', render_activity(visit, "zh", today))
        for today in (date(2027, 1, 10), date(2027, 1, 15)):
            self.assertNotIn('class="role-note"', render_activity(visit, "en", today))


if __name__ == "__main__":
    unittest.main()
