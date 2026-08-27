#!/usr/bin/env python3
"""Summarize a strategy assessment run from scores.csv.

Produces: verdict distribution, criteria averages, zero-score counts,
score distribution, what-if analysis, and near-miss strategies.

Usage:
    python3 scripts/assess-strat/summarize_run.py assessments/20260415-143000/
    python3 scripts/assess-strat/summarize_run.py assessments/20260415-143000/scores.csv
"""

import argparse
import csv
import os
import sys
from collections import Counter

# Must match parse_results.py
CRITERIA = ["Feasibility", "Testability", "Scope", "Architecture"]
APPROVE_THRESHOLD = 6
MAX_SCORE = 8


def load_scores(path):
    """Load scores from CSV file or directory containing scores.csv."""
    if os.path.isdir(path):
        path = os.path.join(path, "scores.csv")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for col in CRITERIA + ["Total"]:
                row[col] = int(row[col])
            rows.append(row)
    return rows


def summarize(rows):
    """Print summary analysis."""
    n = len(rows)
    if n == 0:
        print("No results to summarize.")
        return

    errors = [r for r in rows if r["Verdict"] == "ERROR"]
    assessed = [r for r in rows if r["Verdict"] != "ERROR"]
    na = len(assessed)
    ne = len(errors)

    verdicts = Counter(r["Verdict"] for r in assessed)
    n_approve = verdicts.get("APPROVE", 0)
    n_revise = verdicts.get("REVISE", 0) + verdicts.get("SPLIT", 0)
    n_reject = verdicts.get("REJECT", 0)
    approve_rate = n_approve / na * 100 if na > 0 else 0

    # Averages (exclude errors)
    avgs = {c: sum(r[c] for r in assessed) / na for c in CRITERIA} if na > 0 else {c: 0 for c in CRITERIA}
    avg_total = sum(r["Total"] for r in assessed) / na if na > 0 else 0

    # Zero counts (exclude errors)
    zeros = {c: sum(1 for r in assessed if r[c] == 0) for c in CRITERIA}

    # Score distribution (exclude errors)
    dist = Counter(r["Total"] for r in assessed)

    # What-if: for each criterion, if zeros became 1s, how many more would approve?
    non_approved = [r for r in assessed if r["Verdict"] != "APPROVE"]
    what_if = {}
    for c in CRITERIA:
        extra_approves = 0
        for r in non_approved:
            if r[c] == 0:
                new_total = r["Total"] + 1
                other_zeros = sum(1 for c2 in CRITERIA if c2 != c and r[c2] == 0)
                if new_total >= APPROVE_THRESHOLD and other_zeros == 0:
                    extra_approves += 1
        what_if[c] = extra_approves

    # Near-misses: non-approved with total >= 5 and no zeros (one point from approval)
    near_misses = []
    for r in non_approved:
        zero_criteria = [c for c in CRITERIA if r[c] == 0]
        if r["Total"] >= 5 and len(zero_criteria) == 0:
            near_misses.append((r["ID"], r["Title"][:60], r["Total"], r["Verdict"]))
        elif r["Total"] >= 5 and len(zero_criteria) == 1:
            near_misses.append((r["ID"], r["Title"][:60], r["Total"],
                                f"{r['Verdict']} (zero: {zero_criteria[0]})"))
    near_misses.sort(key=lambda x: -x[2])

    # Output
    print("## Assessment Summary")
    print()
    print(f"- **Total assessed:** {na}")
    print(f"- **Approve:** {n_approve} ({approve_rate:.1f}%)")
    print(f"- **Revise:** {n_revise}")
    print(f"- **Reject:** {n_reject}")
    if ne > 0:
        print(f"- **Errors (data not found):** {ne}")
    print(f"- **Needs attention:** {n_revise + n_reject}")
    print()

    print("### Score Distribution")
    print()
    print("| Score | Count | Bar |")
    print("|-------|-------|-----|")
    for s in range(MAX_SCORE + 1):
        count = dist.get(s, 0)
        bar = "#" * count
        if count > 0:
            print(f"| {s}/{MAX_SCORE}  | {count:>5} | {bar} |")
    print()

    print("### Verdict Distribution")
    print()
    print("| Verdict | Count | % |")
    print("|---------|-------|---|")
    for v in ["APPROVE", "REVISE", "REJECT"]:
        count = verdicts.get(v, 0)
        pct = count / na * 100 if na > 0 else 0
        print(f"| {v} | {count} | {pct:.1f}% |")
    print()

    print("### Criteria Averages")
    print()
    print("| Criterion | Avg  | Zeros | Zero % |")
    print("|-----------|------|-------|--------|")
    for c in CRITERIA:
        zp = zeros[c] / na * 100 if na > 0 else 0
        print(f"| {c:<12} | {avgs[c]:.2f} | {zeros[c]:>5} | {zp:>5.1f}% |")
    print(f"| **Total** | **{avg_total:.2f}** | | |")
    print()

    print("### What-If Analysis (if zeros became 1)")
    print()
    print("| Criterion | Additional approvals |")
    print("|-----------|---------------------|")
    for c in CRITERIA:
        if what_if[c] > 0:
            print(f"| {c:<12} | +{what_if[c]} |")
    if not any(what_if.values()):
        print("| (none)       | Most non-approvals have multiple zeros |")
    print()

    if near_misses:
        print("### Near-Miss Strategies (total >= 5, close to approval)")
        print()
        print("| ID | Title | Total | Status |")
        print("|----|-------|-------|--------|")
        for key, title, total, status in near_misses[:15]:
            print(f"| {key} | {title} | {total}/{MAX_SCORE} | {status} |")
        if len(near_misses) > 15:
            print(f"| ... | ({len(near_misses) - 15} more) | | |")
        print()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="Run directory or scores.csv path")
    args = parser.parse_args()

    rows = load_scores(args.path)
    summarize(rows)


if __name__ == "__main__":
    main()
