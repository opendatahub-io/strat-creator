#!/usr/bin/env python3
"""Parse strategy assessment result files and produce a scores CSV.

Reads individual .result.md files from the assessment directory,
extracts scores for four criteria (Feasibility, Testability, Scope,
Architecture), applies deterministic verdict rules, and writes a CSV.

Verdict rules:
    APPROVE:  total >= 6  AND  no zeros
    REVISE:   total >= 3  AND  at most one zero
    REJECT:   total < 3   OR   2+ zeros

Usage:
    python3 scripts/assess-strat/parse_results.py /path/to/run_dir
    python3 scripts/assess-strat/parse_results.py /path/to/run_dir -o custom-output.csv
"""

import argparse
import csv
import os
import re
import sys

# Configurable criteria list — add a dimension here to extend scoring
CRITERIA = ["Feasibility", "Testability", "Scope", "Architecture"]
MAX_SCORE = len(CRITERIA) * 2  # 8


def compute_verdict(scores):
    """Apply deterministic verdict rules to a scores dict.

    Returns (verdict, needs_attention) tuple.
    """
    total = scores["Total"]
    zero_count = sum(1 for c in CRITERIA if scores[c] == 0)

    # APPROVE: total >= 6 AND no zeros
    if total >= 6 and zero_count == 0:
        return "APPROVE", False

    # REJECT: total < 3 OR 2+ zeros
    if total < 3 or zero_count >= 2:
        return "REJECT", True

    # REVISE: total >= 3 AND at most one zero
    if total >= 3 and zero_count <= 1:
        return "REVISE", True

    # Fallback (should not reach here with valid 0-2 scores)
    return "REJECT", True


def extract_scores(text):
    """Extract scores from an assessment result text.

    Handles variants:
    - | Feasibility | 1/2 | notes |
    - | **Feasibility** | 2 | rationale |
    - | Feasibility | -/2 | Data file not found | (missing → ERROR)
    """
    lower_text = text.lower()
    if "data file not found" in lower_text or "unable to assess" in lower_text:
        if re.search(r"-\s*/\s*2", text):
            result = {c: 0 for c in CRITERIA}
            result["Total"] = 0
            result["Verdict"] = "ERROR"
            result["Needs_Attention"] = True
            return result

    parsed = {c: None for c in CRITERIA}

    for line in text.split("\n"):
        ll = line.strip()
        if not ll.startswith("|"):
            continue

        parts = [p.strip() for p in ll.split("|")]
        if len(parts) < 3:
            continue

        criterion_cell = parts[1]
        score_cell = parts[2]

        # Extract score: N/2 or bare integer. Capture the complete numeric
        # value so a malformed 10/2 cannot silently become 1/2.
        score_m = re.fullmatch(r"\s*(\d+)\s*/\s*2\s*", score_cell)
        if not score_m:
            score_m = re.fullmatch(r"\s*(\d+)\s*", score_cell)
        score = int(score_m.group(1)) if score_m else None

        if score is None:
            continue
        if score not in (0, 1, 2):
            return None

        # Clean criterion for matching
        crit = re.sub(r"[*_()\d/\-]", " ", criterion_cell).strip().lower()

        if "feasib" in crit and parsed["Feasibility"] is None:
            parsed["Feasibility"] = score
        elif "testab" in crit and parsed["Testability"] is None:
            parsed["Testability"] = score
        elif "scope" in crit and "total" not in crit and parsed["Scope"] is None:
            parsed["Scope"] = score
        elif "architect" in crit and parsed["Architecture"] is None:
            parsed["Architecture"] = score

    # Check all criteria were found
    if any(v is None for v in parsed.values()):
        return None

    total = sum(parsed.values())
    parsed["Total"] = total

    verdict, needs_attention = compute_verdict(parsed)
    parsed["Verdict"] = verdict
    parsed["Needs_Attention"] = needs_attention

    return parsed


def extract_title(text):
    """Extract the strategy title from result text."""
    m = re.search(r"(?:\*\*)?TITLE(?:\*\*)?:?\s*(.+)", text)
    if m:
        return m.group(1).strip().strip("*").strip()
    return ""


def sanitize_csv_value(value):
    """Prevent spreadsheet software from evaluating exported cells as formulas."""
    value = str(value)
    return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("result_dir",
                        help="Directory containing .result.md files")
    parser.add_argument("-o", "--output", default=None,
                        help="Output CSV path (default: <result_dir>/scores.csv)")
    args = parser.parse_args()

    result_dir = args.result_dir.rstrip("/")

    # Find all result files
    result_files = sorted(
        [f for f in os.listdir(result_dir) if f.endswith(".result.md")],
        key=lambda f: int(re.search(r"(\d+)", f).group(1)) if re.search(r"(\d+)", f) else 0,
    )

    if not result_files:
        print(f"No .result.md files found in {result_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = os.path.join(result_dir, "scores.csv")

    rows = []
    failed_parse = []

    for filename in result_files:
        key = filename.replace(".result.md", "")
        filepath = os.path.join(result_dir, filename)

        with open(filepath, encoding="utf-8") as f:
            text = f.read()

        scores = extract_scores(text)
        if scores is None:
            failed_parse.append(key)
            continue

        title = extract_title(text)
        rows.append({
            "ID": key,
            "Title": title,
            **scores,
        })

    # Write CSV. Escape every field rather than just untrusted titles: IDs and
    # future score-derived string values are also imported by spreadsheet apps.
    fieldnames = ["ID", "Title"] + CRITERIA + ["Total", "Verdict", "Needs_Attention"]
    csv_rows = [
        {field: sanitize_csv_value(row.get(field, "")) for field in fieldnames}
        for row in rows
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    # Summary
    approved = sum(1 for r in rows if r["Verdict"] == "APPROVE")
    revised = sum(1 for r in rows if r["Verdict"] == "REVISE")
    rejected = sum(1 for r in rows if r["Verdict"] == "REJECT")
    errors = sum(1 for r in rows if r["Verdict"] == "ERROR")

    print(f"Parsed {len(rows)} results -> {output_path}", file=sys.stderr)
    print(f"  Approve: {approved}, Revise: {revised}, Reject: {rejected}",
          file=sys.stderr)
    if errors:
        print(f"  Errors (data not found): {errors}", file=sys.stderr)
    if failed_parse:
        print(f"  Could not parse: {len(failed_parse)} files: {', '.join(failed_parse[:10])}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
