"""Pure helpers of the OpenShell smoke test: allowed-response detection, hashing, polling, paths, guest clients."""
import unittest

from tests.skills.skillimport import add_skill

add_skill("setup-smoketest-openshell")

from openshell_smoketest import config, helpers, process  # noqa: E402
from openshell_smoketest.model import Out  # noqa: E402


class AllowedTest(unittest.TestCase):
    def test_http_2xx_and_3xx_are_allowed(self):
        for text in ("HTTP 200", "HTTP 301", "x HTTP 204 y"):
            self.assertTrue(helpers.allowed(text), text)

    def test_blocked_or_error_statuses_are_not_allowed(self):
        for text in ("BLOCKED EACCES", "HTTP 000BLOCKED", "HTTP 403", "HTTP 502", ""):
            self.assertFalse(helpers.allowed(text), text)


class Sha12Test(unittest.TestCase):
    def test_is_a_stable_12_character_hex_prefix_of_sha256(self):
        self.assertEqual(helpers.sha12("abc"), "ba7816bf8f01")
        self.assertEqual(len(helpers.sha12("")), 12)


class WaitUntilTest(unittest.TestCase):
    def test_returns_none_on_timeout(self):
        self.assertIsNone(helpers.wait_until(lambda: False, timeout=0.05, step=0.01))

    def test_returns_seconds_when_predicate_becomes_true(self):
        calls = []
        secs = helpers.wait_until(lambda: calls.append(1) or len(calls) >= 2, timeout=5, step=0.01)
        self.assertIsNotNone(secs)


class ConfigTest(unittest.TestCase):
    def test_pull_script_path_points_into_the_repo_scripts_folder(self):
        self.assertEqual(config.PULL_SCRIPT, config.REPO_ROOT / "scripts" / "pull_openshell_changes.py")
        self.assertTrue(config.PULL_SCRIPT.exists())

    def test_guest_clients_build_commands_for_the_given_host(self):
        self.assertEqual(list(config.CLIENTS), ["node", "curl", "python3"])
        self.assertEqual(config.CLIENTS["node"]("h.example")[:2], ["node", "-e"])
        self.assertIn("https://h.example", config.CLIENTS["curl"]("h.example")[-1])
        self.assertIn("https://h.example", config.CLIENTS["python3"]("h.example")[-1])

    def test_out_text_joins_and_strips_both_streams(self):
        self.assertEqual(Out(0, " a\n", "b \n").text, "a\nb")


class PhasesTest(unittest.TestCase):
    def test_parses_name_and_last_column_skipping_the_header(self):
        listing = "NAME  CREATED  PHASE\ntrial-1  2026-10-29 06:03:32  Ready\npi  2026-10-28 01:00:00  Provisioning\n"
        from unittest import mock
        with mock.patch.object(process, "osh", lambda *a, **k: Out(0, listing, "")):
            self.assertEqual(process.phases(), {"trial-1": "Ready", "pi": "Provisioning"})
