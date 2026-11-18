"""Regression controls for the inventory, not a product test list."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).with_name("carry_forward_preflight.py")


class InventoryTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.invalid")
        self.workflow = ".github/workflows/stock.yml"
        for path in (self.workflow, "shared", "old-name", "retired"):
            (self.repo / path).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / path).write_text(f"stock {path}\n")
        shared = "first\n" + "middle\n" * 12 + "last\n"
        (self.repo / "shared").write_text(shared)
        self.old = self.commit()
        (self.repo / "shared").write_text(shared.replace("first", "downstream"))
        self.git("mv", "old-name", "new\nname")
        self.git("rm", "retired")
        self.formal = self.commit()
        self.git("switch", "--detach", self.old)
        (self.repo / "shared").write_text(shared.replace("last", "upstream"))
        (self.repo / "old-name").write_text("upstream changed\n")
        self.new = self.commit()
        (self.repo / self.workflow).write_text("unexplained runner drift\n")
        (self.repo / ".github/workflows/grok.yml").write_text("product-owned\n")
        self.candidate = self.commit()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", self.repo, *args], stderr=subprocess.PIPE
        )

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def run_tool(self, *refs, repo=None, env=None):
        return subprocess.run(
            [sys.executable, TOOL, repo or self.repo, *refs],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_inventory_and_restoration(self):
        (self.repo / "shared").write_text("uncommitted, do not touch\n")

        def state():
            return (
                self.git("status", "--porcelain=v1", "-z"),
                self.git("rev-parse", "HEAD"),
                self.git("diff", "--binary"),
                self.git("diff", "--cached", "--binary"),
            )

        before = state()
        run = self.run_tool(self.old, self.formal, self.new, self.candidate)
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual(report["overlap"], ["old-name", "shared"])
        self.assertEqual(report["stock_workflow_drift"], [["M", self.workflow]])
        self.assertEqual(
            report["adds_deletes_renames"]["downstream"],
            [["R100", "old-name", "new\nname"], ["D", "retired"]],
        )
        self.assertIn(
            ["A", ".github/workflows/grok.yml"],
            report["adds_deletes_renames"]["candidate"],
        )
        self.assertEqual(state(), before)
        run = self.run_tool(self.old, self.formal, self.new, self.new)
        self.assertEqual(json.loads(run.stdout)["stock_workflow_drift"], [])

    def test_nested_path_and_ambient_git_dir_do_not_hide_workflow_drift(self):
        run = self.run_tool(
            self.old,
            self.formal,
            self.new,
            self.candidate,
            repo=self.repo / ".github",
            env={**os.environ, "GIT_DIR": "/nonexistent/git-dir"},
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(
            json.loads(run.stdout)["stock_workflow_drift"], [["M", self.workflow]]
        )

    def test_grafted_parent_is_not_accepted_as_history(self):
        (self.repo / ".git/info/grafts").write_text(f"{self.formal} {self.new}\n")
        run = self.run_tool(self.old, self.formal, self.new, self.formal)
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout, "")

    def test_rejects_symbolic_missing_and_wrong_ancestry(self):
        for refs in [
            ("HEAD", self.formal, self.new, self.candidate),
            ("0" * 40, self.formal, self.new, self.candidate),
            (self.new, self.formal, self.new, self.candidate),
            (self.old, self.formal, self.new, self.formal),
        ]:
            with self.subTest(refs=refs):
                run = self.run_tool(*refs)
                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(run.stdout, "")


if __name__ == "__main__":
    unittest.main()
