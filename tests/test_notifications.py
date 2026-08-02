from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


store_mod = load("notification_store")
contact_mod = load("ingest_contact")
pub_mod = load("check_publication_status")
link_mod = load("check_links")
cleanup_mod = load("cleanup_notifications")


class NotificationStoreTests(unittest.TestCase):
    def candidate(self, key="test:1"):
        return {
            "key": key, "type": "system", "title": "Test", "message": "Message",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }

    def test_upsert_preserves_user_state_and_resolution(self):
        store, _ = store_mod.upsert({}, self.candidate())
        row = store["notifications"][0]
        row["starred"] = True
        row["read"] = True
        row["status"] = "resolved"
        refreshed = self.candidate()
        refreshed["message"] = "Updated"
        store, _ = store_mod.upsert(store, refreshed)
        row = store["notifications"][0]
        self.assertTrue(row["starred"])
        self.assertTrue(row["read"])
        self.assertEqual(row["status"], "resolved")
        self.assertEqual(row["message"], "Updated")

    def test_contact_alert_contains_no_personal_data(self):
        notification = contact_mod.build_notification({
            "event_id": "opaque-123", "received_at": "2026-07-31T12:00:00Z",
            "name": "Prof. Smith", "email": "smith@example.com", "message": "Private invitation",
        })
        serialized = json.dumps(notification)
        self.assertNotIn("Prof. Smith", serialized)
        self.assertNotIn("smith@example.com", serialized)
        self.assertNotIn("Private invitation", serialized)
        self.assertEqual(notification["key"], "contact:opaque-123")


class AutomatedNotificationTests(unittest.TestCase):
    def test_crossref_candidate_creates_publish_notification(self):
        site = {"publications": [{
            "id": "paper-1", "year": 2026, "group_id": "preprints",
            "title": {"en": "A Test Paper", "zh": ""},
            "authors": {"en": "Hung-Chun Tsui", "zh": "崔鴻竣"},
        }]}
        fixture = {"paper-1": [{
            "DOI": "10.1234/example", "title": ["A Test Paper"],
            "author": [{"given": "Hung-Chun", "family": "Tsui"}],
            "container-title": ["Example Journal"], "URL": "https://doi.org/10.1234/example",
            "published-print": {"date-parts": [[2026]]},
        }]}
        updated, count = pub_mod.run(site, {}, fixture=fixture)
        self.assertEqual(count, 1)
        item = updated["notifications"][0]
        self.assertEqual(item["type"], "publication_status")
        self.assertEqual(item["payload"]["doi"], "10.1234/example")

    def test_link_checker_only_flags_confirmed_404_or_410(self):
        site = {"publications": [{"id": "p", "title": {"en": "P"}, "pdf_url": "https://example.test/dead"}], "items": [], "settings": {"footer": {"items": []}}}
        updated, broken, resolved = link_mod.run(site, {"people": []}, {}, fixture={"https://example.test/dead": 404})
        self.assertEqual((broken, resolved), (1, 0))
        self.assertEqual(updated["notifications"][0]["type"], "broken_link")

    def test_cleanup_keeps_starred_old_notification(self):
        old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat().replace("+00:00", "Z")
        base = {"retention_days": 60, "notifications": [
            {**NotificationStoreTests().candidate("old:drop"), "updated_at": old},
            {**NotificationStoreTests().candidate("old:keep"), "updated_at": old, "starred": True},
        ]}
        cleaned, removed = cleanup_mod.cleanup_store(base, datetime.now(timezone.utc))
        self.assertEqual(removed, 1)
        self.assertEqual([x["key"] for x in cleaned["notifications"]], ["old:keep"])


class StaticNotificationIntegrationTests(unittest.TestCase):
    def test_admin_and_workflows_are_wired(self):
        admin = (ROOT / "admin/index.html").read_text(encoding="utf-8")
        script = (ROOT / "admin/notifications.js").read_text(encoding="utf-8")
        self.assertRegex(admin, r'<script src="notifications\.js\?v=[^"]+"></script>')
        for token in ["通知中心", "data-general-star", "notificationSearch", "fetchDeploymentStatus", "轉為 Published", "前往修改"]:
            self.assertIn(token, script)
        for path in [
            ".github/workflows/check-publication-status.yml", ".github/workflows/check-links.yml",
            ".github/workflows/cleanup-notifications.yml", ".github/workflows/ingest-contact.yml",
        ]:
            self.assertTrue((ROOT / path).exists(), path)

    def test_worker_never_dispatches_private_fields(self):
        worker = (ROOT / "integrations/contact-worker.js").read_text(encoding="utf-8")
        dispatch_section = worker.split("client_payload:", 1)[1]
        self.assertIn("event_id", dispatch_section)
        self.assertIn("received_at", dispatch_section)
        self.assertNotIn("email", dispatch_section.split("});", 1)[0])
        self.assertNotIn("message", dispatch_section.split("});", 1)[0])


if __name__ == "__main__":
    unittest.main()
