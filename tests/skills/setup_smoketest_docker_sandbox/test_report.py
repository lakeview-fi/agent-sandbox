"""Report and record rendering, and the check-group runner of the Docker Sandboxes smoke test."""
import argparse
import contextlib
import io
import re
import unittest
from pathlib import Path
from unittest import mock

from tests.skills.skillimport import add_skill

add_skill("setup-smoketest-docker-sandbox")

from sbx_smoketest import record, report, runner  # noqa: E402
from sbx_smoketest.model import FAIL, INFO, PASS, SKIP, Check, Ctx  # noqa: E402
from sbx_smoketest.step_agent import agent_task  # noqa: E402


def captured(func, *args) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args)
    return buf.getvalue()


class PrintTableTest(unittest.TestCase):
    def test_line_format_is_status_padded_to_four_name_and_first_detail_row(self):
        out = captured(report.print_table, [Check("x", PASS, "ok\nsecond"), Check("y", SKIP, "")])
        self.assertEqual(out.splitlines(), ["[PASS] x: ok", "[SKIP] y: "])

    def test_info_prints_continuation_rows_indented(self):
        out = captured(report.print_table, [Check("obs", INFO, "first\nsecond\nthird")])
        self.assertEqual(out.splitlines(), ["[INFO] obs: first", "         second", "         third"])


class AgentVerifiedTest(unittest.TestCase):
    def test_requires_a_passing_8e(self):
        self.assertTrue(report.agent_verified([Check("8e task", PASS)]))
        self.assertFalse(report.agent_verified([Check("8e task", SKIP)]))
        self.assertFalse(report.agent_verified([Check("1 other", PASS)]))


class PrintReportTest(unittest.TestCase):
    def test_counts_fail_and_skip_and_lists_them(self):
        out = captured(report.print_report, [Check("8e t", SKIP, "why"), Check("a", FAIL, "bad\nmore"), Check("b", PASS)])
        self.assertIn("SETUP NOT VERIFIED", out)
        self.assertIn("1 FAIL, 1 SKIP", out)
        self.assertIn("- FAIL a: bad", out)
        self.assertIn("- SKIP 8e t: why", out)

    def test_verified_banner_and_clean_list(self):
        out = captured(report.print_report, [Check("8e t", PASS)])
        self.assertIn("SETUP VERIFIED", out)
        self.assertIn("- no FAIL or SKIP", out)


class RenderTest(unittest.TestCase):
    def test_markdown_table_escapes_pipes_and_newlines_and_appends_kit_hosts(self):
        checks = [Check("a", PASS, "x|y\nz"), Check("kit policy hosts (record these)", INFO, "HOSTS")]
        text = record.render("trial-1", {"version": "sbx v1"}, checks, 3)
        self.assertRegex(text, r"## Run 3 \(\d{4}-\d\d-\d\d, `sbx v1`, ")
        self.assertIn("| a | PASS | x\\|y<br>z |", text)
        self.assertIn("```\nHOSTS\n```", text)

    def test_detail_is_cut_to_400_characters(self):
        text = record.render("n", {"version": "v"}, [Check("a", PASS, "x" * 500)], 1)
        self.assertIn("| a | PASS | " + "x" * 400 + " |", text)


class RunnerTest(unittest.TestCase):
    def ctx(self, created: bool) -> Ctx:
        ctx = Ctx("n", Path("."), {}, argparse.Namespace())
        ctx.created = created
        return ctx

    def test_crashing_group_becomes_a_fail_and_does_not_stop_the_others(self):
        def step_boom(ctx):
            raise RuntimeError("x")

        def step_ok(ctx):
            return [Check("fine", PASS)]

        checks = [c for step in (step_boom, step_ok) for c in runner._guarded(step, self.ctx(True))]
        self.assertEqual([(c.name, c.status) for c in checks], [("step_boom", FAIL), ("fine", PASS)])
        self.assertIn("RuntimeError('x')", checks[0].detail)

    def test_every_group_is_skipped_when_the_sandbox_was_not_created(self):
        with mock.patch.object(runner, "_guarded", lambda step, ctx: [Check(step.__name__, FAIL, "create failed")]):
            checks = runner.run_checks(self.ctx(False))
        skipped = [c for c in checks if c.status == SKIP]
        self.assertEqual(len(skipped), len(runner.STEPS))
        self.assertTrue(all(re.fullmatch(r"step_\w+", c.name) for c in skipped))


class AgentTaskSkipTest(unittest.TestCase):
    def test_no_inference_skips_8e_without_touching_the_sandbox(self):
        ctx = Ctx("n", Path("."), {}, argparse.Namespace(no_inference=True))
        check = agent_task(ctx, "claude", True, [])
        self.assertEqual((check.name, check.status), ("8e agent completes a file-reading task", SKIP))

    def test_failed_8c_makes_8e_a_fail(self):
        ctx = Ctx("n", Path("."), {}, argparse.Namespace(no_inference=False))
        check = agent_task(ctx, "claude", True, [Check("8c LLM inference through the agent", FAIL)])
        self.assertEqual(check.status, FAIL)
