"""Report and record rendering, the runner, and the AgentSpec table of the OpenShell smoke test."""
import argparse
import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from tests.skills.skillimport import add_skill

add_skill("setup-smoketest-openshell")

from openshell_smoketest import record, report, runner  # noqa: E402
from openshell_smoketest.agent_task import AGENTS, agent_task  # noqa: E402
from openshell_smoketest.model import FAIL, INFO, PASS, SKIP, Check, Ctx  # noqa: E402


def captured(func, *args) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args)
    return buf.getvalue()


def make_ctx(**kw) -> Ctx:
    ctx = Ctx("n", {}, argparse.Namespace(agent="claude", no_inference=False, **kw), Path("."))
    return ctx


class ReportTest(unittest.TestCase):
    def test_print_table_format(self):
        out = captured(report.print_table, [Check("x", PASS, "ok\nhidden"), Check("o", INFO, "a\nb")])
        self.assertEqual(out.splitlines(), ["[PASS] x: ok", "[INFO] o: a", "         b"])

    def test_agent_verified_requires_every_8e_to_pass(self):
        self.assertTrue(report.agent_verified([Check("8e t", PASS)]))
        self.assertFalse(report.agent_verified([Check("8e t", PASS), Check("8e t2", FAIL)]))
        self.assertFalse(report.agent_verified([]))

    def test_print_report_counts_and_lists_fail_and_skip(self):
        out = captured(report.print_report, [Check("8e t", SKIP, "why"), Check("a", FAIL, "bad")])
        self.assertIn("SETUP NOT VERIFIED", out)
        self.assertIn("1 FAIL, 1 SKIP", out)
        self.assertIn("- SKIP 8e t: why", out)


class RenderTest(unittest.TestCase):
    def test_table_escapes_pipes_and_appends_policy_listings(self):
        checks = [Check("a", PASS, "x|y\nz"), Check("effective network policy (base)", INFO, "POLICY")]
        text = record.render("trial-1", {"version": "openshell 1"}, checks, 2, argparse.Namespace(image="img:local"))
        self.assertIn("## Run 2 (", text)
        self.assertIn("from image `img:local`", text)
        self.assertIn("| a | PASS | x\\|y<br>z |", text)
        self.assertIn("effective network policy (base):\n```\nPOLICY\n```", text)


class RunnerTest(unittest.TestCase):
    def test_crashing_group_becomes_a_fail(self):
        def step_boom(ctx):
            raise ValueError("v")

        (check,) = runner._guarded(step_boom, make_ctx())
        self.assertEqual((check.name, check.status), ("step_boom", FAIL))
        self.assertIn("ValueError('v')", check.detail)

    def test_groups_are_skipped_when_the_sandbox_was_not_created(self):
        with mock.patch.object(runner, "_guarded", lambda step, ctx: [Check(step.__name__, FAIL, "create failed")]):
            checks = runner.run_checks(make_ctx())
        self.assertEqual(sum(c.status == SKIP for c in checks), len(runner.STEPS))


class AgentTaskSkipTest(unittest.TestCase):
    def test_agents_table_has_claude_and_pi(self):
        self.assertEqual(set(AGENTS), {"claude", "pi"})
        self.assertTrue(AGENTS["claude"].needs_rule)
        self.assertFalse(AGENTS["pi"].needs_rule)

    def test_no_inference_skips_8e(self):
        ctx = make_ctx()
        ctx.args.no_inference = True
        check = agent_task(ctx, True)
        self.assertEqual((check.name, check.status), ("8e claude agent completes a file-reading task", SKIP))

    def test_unknown_agent_skips_8e(self):
        ctx = make_ctx()
        ctx.args.agent = "nope"
        self.assertEqual(agent_task(ctx, True).status, SKIP)

    def test_no_provider_skips_8e(self):
        self.assertEqual(agent_task(make_ctx(), True).status, SKIP)
