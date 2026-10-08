from __future__ import annotations

import sys
from pathlib import Path

from plugin_build.build import PackageError, build_from_head, repository_root


def main() -> int:
    try:
        package = build_from_head(repository_root(Path.cwd()))
    except PackageError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 1
    print(f"{package.source_commit} {package.version} {package.zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
