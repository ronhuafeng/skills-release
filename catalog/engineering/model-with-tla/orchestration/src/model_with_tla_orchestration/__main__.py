from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import CheckInputError, ToolPrerequisiteError, check_model


def emit(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tla-check")
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check")
    check.add_argument("--module", type=Path, required=True)
    check.add_argument("--config", type=Path)
    check.add_argument("--expect", required=True)
    check.add_argument("--java", type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = check_model(
            module=args.module,
            config=args.config,
            expectation=args.expect,
            java=args.java,
        )
    except CheckInputError as exc:
        emit({"schema_version": 1, "status": "invalid", "error": str(exc)})
        return 2
    except (OSError, ToolPrerequisiteError) as exc:
        emit({"schema_version": 1, "status": "blocked", "error": str(exc)})
        return 3
    emit(result.to_dict())
    if result.status == "matched":
        return 0
    if result.status == "mismatch":
        return 4
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
