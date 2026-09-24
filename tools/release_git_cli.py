#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

try:
    from tools import release_git
except ModuleNotFoundError:
    import release_git


def main() -> int:
    proc = release_git.run_stream(
        Path.cwd(),
        *sys.argv[1:],
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
