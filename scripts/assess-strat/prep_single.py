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
    single_dir = args.single_dir
    os.makedirs(single_dir, exist_ok=True)

    for suffix in (".result.md",):
        path = os.path.join(single_dir, f"{key}{suffix}")
        if os.path.exists(path):
            os.remove(path)
            print(f"REMOVED={path}")

    print(f"SINGLE_DIR={single_dir}")


if __name__ == "__main__":
    main()
