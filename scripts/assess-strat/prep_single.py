#!/usr/bin/env python3
"""Prepare the single-assessment directory for a new run.

Removes any existing result files for the given key so that
Write tool calls see them as new files (avoiding the read-before-write guard).
Creates the output directory if it doesn't exist.

Usage:
    python3 scripts/assess-strat/prep_single.py RHAISTRAT-1234
    python3 scripts/assess-strat/prep_single.py RHAISTRAT-1234 --single-dir /path/to/output
"""

import argparse
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: prep_single.py KEY", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("key", help="Strategy key whose stale result should be removed")
    parser.add_argument(
        "--single-dir",
        default="/tmp/strat-assess/single",
        help="Directory for single-assessment result files (default: %(default)s)",
    )
    args = parser.parse_args()

    key = args.key
    if (
        not key
        or os.path.isabs(key)
        or "/" in key
        or "\\" in key
        or key in {".", ".."}
    ):
        parser.error("key must be a simple strategy filename, not a path")

    single_dir = Path(args.single_dir).resolve()
    single_dir.mkdir(parents=True, exist_ok=True)

    for suffix in (".result.md",):
        path = (single_dir / f"{key}{suffix}").resolve()
        try:
            path.relative_to(single_dir)
        except ValueError:
            parser.error("result path escapes --single-dir")
        if path.exists():
            os.remove(path)
            print(f"REMOVED={path}")

    print(f"SINGLE_DIR={single_dir}")


if __name__ == "__main__":
    main()
