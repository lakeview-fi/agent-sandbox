"""Pure helpers of the Docker Sandboxes smoke test: blocked-response detection, path mapping, polling, paths."""
import os
import unittest
from pathlib import Path

from tests.skills.skillimport import add_skill

add_skill("setup-smoketest-docker-sandbox")

from sbx_smoketest import config, helpers  # noqa: E402
from sbx_smoketest.model import Out  # noqa: E402


class IsBlockedTest(unittest.TestCase):
    def test_approval_prompt_and_403_are_blocked(self):
        self.assertTrue(helpers.is_blocked("Approval required for example.com:443."))
        self.assertTrue(helpers.is_blocked("HTTP 403 Forbidden"))

    def test_real_page_is_not_blocked_even_if_it_mentions_403(self):
        self.assertFalse(helpers.is_blocked("<h1>Example Domain</h1> error 403 in text"))

    def test_empty_output_is_not_blocked(self):
        self.assertFalse(helpers.is_blocked(""))


class GuestPathTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "drive-letter mapping applies on Windows hosts only")
    def test_windows_path_maps_to_lowercase_drive_prefix(self):
        self.assertEqual(helpers.guest_path(Path("C:\\Users\\a\\b")), "/c/Users/a/b")

    @unittest.skipIf(os.name == "nt", "POSIX hosts see the same path in the guest")
    def test_posix_path_is_unchanged(self):
        self.assertEqual(helpers.guest_path(Path("/home/a/b")), "/home/a/b")


class WaitUntilTest(unittest.TestCase):
    def test_returns_elapsed_seconds_when_true_immediately(self):
        self.assertLess(helpers.wait_until(lambda: True, timeout=5), 1.0)

    def test_returns_none_on_timeout(self):
        self.assertIsNone(helpers.wait_until(lambda: False, timeout=0.05, step=0.01))

    def test_polls_until_predicate_turns_true(self):
        calls = []
        secs = helpers.wait_until(lambda: calls.append(1) or len(calls) >= 3, timeout=5, step=0.01)
        self.assertIsNotNone(secs)
        self.assertEqual(len(calls), 3)


class ModelAndConfigTest(unittest.TestCase):
    def test_out_text_joins_and_strips_both_streams(self):
        self.assertEqual(Out(0, " a\n", "b \n").text, "a\nb")

    def test_pull_script_path_points_into_the_repo_scripts_folder(self):
        self.assertEqual(config.PULL_SCRIPT, config.REPO_ROOT / "scripts" / "pull_docker_commits.py")
        self.assertTrue(config.PULL_SCRIPT.exists())

    def test_default_model_is_unchanged(self):
        self.assertEqual(config.DEFAULT_MODEL, "claude-haiku-5-5")
