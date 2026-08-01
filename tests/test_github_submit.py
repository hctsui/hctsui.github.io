from __future__ import annotations

import subprocess
import unittest

from _contracts import ROOT, read


class GitHubSubmitWorkerContracts(unittest.TestCase):
    def test_worker_module_parses(self) -> None:
        subprocess.run(
            ["node", "--input-type=module", "--check"],
            input=read("integrations/contact-worker.js"),
            text=True,
            check=True,
            cwd=ROOT,
        )

    def test_oauth_session_submit_and_duplicate_protection(self) -> None:
        subprocess.run(
            ["node", "tests/github_submit_worker_harness.mjs"],
            check=True,
            cwd=ROOT,
        )

    def test_worker_keeps_secrets_server_side_and_scopes_login(self) -> None:
        worker = read("integrations/contact-worker.js")
        for marker in (
            "GITHUB_OAUTH_CLIENT_SECRET",
            "CMS_SESSION_SECRET",
            "CMS_ALLOWED_GITHUB_LOGIN",
            'kind: "session"',
            'Path=/cms/auth',
            "HttpOnly; Secure; SameSite=Lax",
            'authorization: `Bearer ${env.GITHUB_TOKEN}`',
            "gzip-base64:",
            "cms-request:",
            'url.pathname === "/cms/submit"',
            'url.pathname === "/cms/session"',
        ):
            self.assertIn(marker, worker)
        admin = read("admin/github-submit.js")
        self.assertNotIn("GITHUB_TOKEN", admin)
        self.assertNotIn("GITHUB_OAUTH_CLIENT_SECRET", admin)


if __name__ == "__main__":
    unittest.main()
