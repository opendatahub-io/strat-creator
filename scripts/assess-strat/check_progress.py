#!/usr/bin/env python3
"""Check progress of an assessment run.

Reports completed result count vs total expected strategies.

Usage:
    python3 scripts/assess-strat/check_progress.py /path/to/run_dir
"""

import os
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: check_progress.py RUN_DIR", file=sys.stderr)
        sys.exit(1)

    run_dir = sys.argv[1]

    if not os.path.isdir(run_dir):
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Count completed results
    completed = len([f for f in os.listdir(run_dir) if f.endswith(".result.md")])

    # Determine total from the strategy directory recorded at setup time
    total = 0
    strat_dir_file = os.path.join(run_dir, "strat_dir.txt")
    if os.path.exists(strat_dir_file):
        with open(strat_dir_file, "r", encoding="utf-8") as f:
            strat_dir = f.read().strip()
        if os.path.isdir(strat_dir):
            total = len([f for f in os.listdir(strat_dir)
                         if f.endswith(".md") and not f.endswith("-review.md")])

    print(f"COMPLETED={completed}")
    print(f"TOTAL={total}")
    print(f"REMAINING={max(total - completed, 0)}")


if __name__ == "__main__":
    main()
