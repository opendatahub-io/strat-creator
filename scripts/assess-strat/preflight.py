#!/usr/bin/env python3
"""Preflight checks for a strategy assessment run.

Checks strategy directory and current run state, outputting structured
results for the coordinator to parse.

Usage:
    python3 scripts/assess-strat/preflight.py /path/to/strategies
"""

import os
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: preflight.py STRAT_DIR", file=sys.stderr)
        sys.exit(1)

    strat_dir = sys.argv[1]

    # Check strategy directory
    strat_count = 0
    if os.path.isdir(strat_dir):
        strat_count = len([f for f in os.listdir(strat_dir)
                           if f.endswith(".md") and not f.endswith("-review.md")])
    print(f"STRAT_DIR={os.path.abspath(strat_dir) if os.path.isdir(strat_dir) else strat_dir}")
    print(f"STRAT_DIR_EXISTS={'true' if os.path.isdir(strat_dir) else 'false'}")
    print(f"STRAT_COUNT={strat_count}")

    # Check current run state
    assess_base = "assessments"
    current_link = os.path.join(assess_base, "current")

    if os.path.islink(current_link):
        target = os.path.join(assess_base, os.readlink(current_link))
        if os.path.isdir(target):
            has_scores = os.path.exists(os.path.join(target, "scores.csv"))
            assessed = len([f for f in os.listdir(target) if f.endswith(".result.md")])
            print(f"CURRENT_RUN={os.path.abspath(target)}")
            print(f"CURRENT_ASSESSED={assessed}")
            print(f"CURRENT_COMPLETE={'true' if has_scores else 'false'}")
        else:
            print("CURRENT_RUN=none")
    else:
        print("CURRENT_RUN=none")


if __name__ == "__main__":
    main()
