#!/usr/bin/env python3
"""Set up an assessment run directory with resume support.

Checks for an existing incomplete run (current symlink with no scores.csv),
creates a new timestamped directory if needed, writes pending keys to a queue
file (queue.txt), and outputs run metadata.

Usage:
    python3 scripts/assess-strat/setup_run.py /path/to/strategies
    python3 scripts/assess-strat/setup_run.py /path/to/strategies --limit 20
"""

import argparse
import os
import sys
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("strat_dir", help="Directory containing strategy .md files")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of pending keys (0 = all)")
    parser.add_argument("--assess-dir", default="assessments",
                        help="Base assessments directory (default: assessments)")
    args = parser.parse_args()

    strat_dir = args.strat_dir

    # Check strategy directory exists
    if not os.path.isdir(strat_dir):
        print(f"ERROR: Strategy directory not found at {strat_dir}", file=sys.stderr)
        sys.exit(1)

    # Get all strategy keys from directory
    all_keys = sorted(
        [f.replace(".md", "") for f in os.listdir(strat_dir)
         if f.endswith(".md") and not f.endswith("-review.md")],
        key=lambda k: int(k.split("-")[-1]) if k.split("-")[-1].isdigit() else 0,
    )

    if not all_keys:
        print(f"ERROR: No strategy files found in {strat_dir}", file=sys.stderr)
        sys.exit(1)

    # Resume logic
    assess_base = args.assess_dir
    os.makedirs(assess_base, exist_ok=True)
    current_link = os.path.join(assess_base, "current")
    run_dir = None
    resuming = False

    if os.path.islink(current_link):
        target = os.path.join(assess_base, os.readlink(current_link))
        if os.path.isdir(target) and not os.path.exists(os.path.join(target, "scores.csv")):
            run_dir = target
            resuming = True

    if run_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = os.path.join(assess_base, timestamp)
        os.makedirs(run_dir, exist_ok=True)
        # Update symlink
        tmp_link = current_link + ".tmp"
        os.symlink(os.path.basename(run_dir), tmp_link)
        os.replace(tmp_link, current_link)

    # Find already-assessed keys
    assessed = set()
    if os.path.isdir(run_dir):
        assessed = {
            f.replace(".result.md", "")
            for f in os.listdir(run_dir)
            if f.endswith(".result.md")
        }

    # Pending keys
    pending = [k for k in all_keys if k not in assessed]
    if args.limit > 0:
        pending = pending[:args.limit]

    # Write pending keys to queue file in run directory
    run_dir_abs = os.path.abspath(run_dir)
    queue_file = os.path.join(run_dir_abs, "queue.txt")
    with open(queue_file, "w", encoding="utf-8") as f:
        for key in pending:
            f.write(key + "\n")

    # Store strategy directory path for agents to find source files
    strat_dir_abs = os.path.abspath(strat_dir)
    strat_dir_file = os.path.join(run_dir_abs, "strat_dir.txt")
    with open(strat_dir_file, "w", encoding="utf-8") as f:
        f.write(strat_dir_abs + "\n")

    # Output
    print(f"RUN_DIR={run_dir_abs}")
    print(f"STRAT_DIR={strat_dir_abs}")
    print(f"TOTAL_STRATEGIES={len(all_keys)}")
    print(f"ALREADY_ASSESSED={len(assessed)}")
    print(f"PENDING={len(pending)}")
    print(f"QUEUE_FILE={queue_file}")
    print(f"RESUMING={'true' if resuming else 'false'}")

    if resuming:
        print(f"Resuming run: {run_dir_abs} ({len(assessed)} done, {len(pending)} remaining)",
              file=sys.stderr)
    else:
        print(f"New run: {run_dir_abs} ({len(pending)} strategies)", file=sys.stderr)


if __name__ == "__main__":
    main()
