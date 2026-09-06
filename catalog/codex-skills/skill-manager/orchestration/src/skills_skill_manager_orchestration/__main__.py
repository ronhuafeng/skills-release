from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .enrollment import enroll_host
from .core import (
    BlockedOperation,
    IncompleteEvidence,
    apply_sync_plan,
    apply_vendor_plan,
    inspect_registry,
    plan_sync,
    plan_vendor,
)
from .fleet import FleetConfigError, fleet_audit, render_host_profile
from .host_runtime import handle_host_request, runtime_identity
from .reconcile import apply_fleet_revision


def emit(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def _add_plan_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> None:
    command = subparsers.add_parser(name)
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact", type=Path, required=True)


def _add_apply_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
) -> None:
    command = subparsers.add_parser(name)
    command.add_argument("--artifact", type=Path, required=True)
    command.add_argument("--digest", required=True)
    command.add_argument("--approve-destructive", action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-manager")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect")
    inspect.add_argument("--profile", type=Path, required=True)
    inspect.add_argument(
        "--registry",
        nargs=2,
        action="append",
        metavar=("SCOPE", "DIRECTORY"),
        default=[],
    )
    inspect.add_argument("--source-root", type=Path, action="append", default=[])

    render = sub.add_parser("render-profile")
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--host-id", required=True)

    audit = sub.add_parser("fleet-audit")
    audit.add_argument("--manifest", type=Path, required=True)
    audit.add_argument("--host-id", action="append")

    enroll = sub.add_parser("enroll")
    enroll.add_argument("--manifest", type=Path, required=True)
    enroll.add_argument("--revision", required=True)

    apply = sub.add_parser("apply")
    apply.add_argument("--manifest", type=Path, required=True)
    apply.add_argument("--revision", required=True)

    # Private mechanical interfaces used by the Agent-owned composition.
    _add_plan_command(sub, "_link-plan")
    _add_apply_command(sub, "_link-apply")
    _add_plan_command(sub, "_snapshot-plan")
    _add_apply_command(sub, "_snapshot-apply")
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv == ["--identity"]:
        try:
            emit(runtime_identity())
            return 0
        except (ImportError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 2
    if raw_argv == ["_host"]:
        try:
            emit(handle_host_request(json.load(sys.stdin)))
            return 0
        except (FileNotFoundError, OSError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 3
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(exc, file=sys.stderr)
            return 2

    args = _parser().parse_args(raw_argv)
    try:
        if args.command == "inspect":
            emit(
                inspect_registry(
                    args.profile,
                    [(scope, Path(directory)) for scope, directory in args.registry],
                    args.source_root,
                )
            )
        elif args.command == "render-profile":
            emit(render_host_profile(args.manifest, args.host_id))
        elif args.command == "fleet-audit":
            result = fleet_audit(args.manifest, args.host_id)
            emit(result)
            return {"converged": 0, "drifted": 3, "incomplete": 4}[result["status"]]
        elif args.command == "enroll":
            emit(enroll_host(args.manifest, args.revision))
        elif args.command == "apply":
            result = apply_fleet_revision(args.manifest, args.revision)
            emit(result)
            return 0 if result["status"] == "success" else 3
        elif args.command == "_link-plan":
            result = plan_sync(json.loads(args.request.read_text()), args.artifact)
            emit(result)
            return 3 if result["status"] == "blocked" else 0
        elif args.command == "_link-apply":
            emit(
                apply_sync_plan(
                    args.artifact,
                    args.digest,
                    args.approve_destructive,
                )
            )
        elif args.command == "_snapshot-plan":
            result = plan_vendor(json.loads(args.request.read_text()), args.artifact)
            emit(result)
            return 3 if result["status"] == "blocked" else 0
        elif args.command == "_snapshot-apply":
            emit(
                apply_vendor_plan(
                    args.artifact,
                    args.digest,
                    args.approve_destructive,
                )
            )
    except FleetConfigError as exc:
        emit({"status": "invalid", "validation_blockers": [str(exc)]})
        return 2
    except IncompleteEvidence as exc:
        print(exc, file=sys.stderr)
        return 4
    except BlockedOperation as exc:
        print(exc, file=sys.stderr)
        return 3
    except KeyError as exc:
        print(f"invalid request: missing required field {exc.args[0]}", file=sys.stderr)
        return 2
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
