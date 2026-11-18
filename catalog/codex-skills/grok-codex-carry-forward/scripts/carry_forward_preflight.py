"""Inventory a carry-forward from Git objects only. No product acceptance verdict."""

import argparse
import json
import os
import re
import subprocess
import sys


def inventory(repo, old_stock, old_grok, new_stock, candidate):
    # Hook/shell context must not redirect this command to a different repository.
    local_env = (
        subprocess.check_output(["git", "rev-parse", "--local-env-vars"])
        .decode()
        .splitlines()
    )
    env = {k: v for k, v in os.environ.items() if k not in local_env}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_GRAFT_FILE=os.devnull)

    def git(*args):
        return subprocess.run(
            [
                "git",
                "-c",
                "advice.graftFileDeprecated=false",
                "--no-lazy-fetch",
                "--no-replace-objects",
                "-C",
                repo,
                *args,
            ],
            stdout=subprocess.PIPE,
            check=True,
            env=env,
        ).stdout

    refs = dict(
        old_stock=old_stock, old_grok=old_grok, new_stock=new_stock, candidate=candidate
    )
    for name, sha in refs.items():
        if (
            not re.fullmatch(r"[0-9a-f]{40}", sha)
            or git("cat-file", "-t", sha) != b"commit\n"
        ):
            raise ValueError(f"{name}: expected a full GitHub commit SHA")
    for parent, child in [(old_stock, old_grok), (new_stock, candidate)]:
        try:
            git("merge-base", "--is-ancestor", parent, child)
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                f"cannot prove {parent} is an ancestor of {child}; check pins/history"
            ) from exc

    def diff(base, tip):
        # NUL records preserve arbitrary Git path bytes; keep BOTH ends of a rename.
        fields = iter(
            git(
                "diff-tree",
                "--no-relative",
                "--no-commit-id",
                "-r",
                "-z",
                "--name-status",
                "--no-ext-diff",
                "--no-textconv",
                "--ignore-submodules=none",
                "--find-renames=50%",
                "-l1000",
                base,
                tip,
                "--",
            ).split(b"\0")[:-1]
        )
        changes = []
        for status in fields:
            paths = [
                os.fsdecode(next(fields))
                for _ in range(2 if status.startswith(b"R") else 1)
            ]
            changes.append([status.decode("ascii"), *paths])
        return changes

    comparisons = {
        "downstream": diff(old_stock, old_grok),
        "upstream": diff(old_stock, new_stock),
        "candidate": diff(new_stock, candidate),
    }
    paths = {
        label: {path for _, *ends in changes for path in ends}
        for label, changes in comparisons.items()
    }
    stock_workflows = {
        os.fsdecode(path)
        for sha in (old_stock, new_stock)
        for path in git(
            "ls-tree",
            "--full-tree",
            "-rz",
            "--name-only",
            sha,
            "--",
            ".github/workflows/",
        ).split(b"\0")
        if path
    }
    return {
        "scope": "Git path inventory only; no semantic, test or CI verdict",
        **refs,
        "overlap": sorted(paths["downstream"] & paths["upstream"]),
        "stock_workflow_drift": [
            change
            for change in comparisons["candidate"]
            if stock_workflows.intersection(change[1:])
        ],
        "adds_deletes_renames": {
            label: [c for c in changes if c[0][0] in "ADR"]
            for label, changes in comparisons.items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("repo", "old_stock", "old_grok", "new_stock", "candidate"):
        parser.add_argument(arg)
    try:
        report = inventory(**vars(parser.parse_args()))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(f"preflight: {exc}")
    print(json.dumps(report, indent=2, ensure_ascii=True))
