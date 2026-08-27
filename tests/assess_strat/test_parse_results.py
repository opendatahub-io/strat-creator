"""Tests for parse_results.py — verdict rules, score extraction, CLI."""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "assess-strat"))
from conftest import make_result_file, run_script
from parse_results import compute_verdict, extract_scores, extract_title

# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------

class TestComputeVerdict:
    def _scores(self, f, t, s, a):
        return {
            "Feasibility": f, "Testability": t,
            "Scope": s, "Architecture": a,
            "Total": f + t + s + a,
        }

    def test_approve_perfect(self):
        assert compute_verdict(self._scores(2, 2, 2, 2)) == ("APPROVE", False)

    def test_approve_threshold(self):
        assert compute_verdict(self._scores(2, 2, 1, 1)) == ("APPROVE", False)

    def test_approve_boundary_total_6(self):
        assert compute_verdict(self._scores(1, 2, 2, 1)) == ("APPROVE", False)

    def test_revise_total_5_one_zero(self):
        assert compute_verdict(self._scores(0, 2, 2, 1)) == ("REVISE", True)

    def test_revise_total_3_one_zero(self):
        assert compute_verdict(self._scores(0, 1, 1, 1)) == ("REVISE", True)

    def test_revise_total_4_no_zeros(self):
        assert compute_verdict(self._scores(1, 1, 1, 1)) == ("REVISE", True)

    def test_revise_total_5_no_zeros(self):
        assert compute_verdict(self._scores(2, 1, 1, 1)) == ("REVISE", True)

    def test_reject_total_2(self):
        assert compute_verdict(self._scores(1, 1, 0, 0)) == ("REJECT", True)

    def test_reject_two_zeros_high_total(self):
        assert compute_verdict(self._scores(0, 0, 2, 2)) == ("REJECT", True)

    def test_reject_all_zeros(self):
        assert compute_verdict(self._scores(0, 0, 0, 0)) == ("REJECT", True)

    def test_reject_total_1(self):
        assert compute_verdict(self._scores(0, 0, 0, 1)) == ("REJECT", True)


# ---------------------------------------------------------------------------
# extract_scores
# ---------------------------------------------------------------------------

class TestExtractScores:
    def test_standard_table(self):
        text = """\
| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | 2/2 | good |
| Testability | 1/2 | ok |
| Scope | 2/2 | fine |
| Architecture | 1/2 | decent |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Feasibility"] == 2
        assert result["Testability"] == 1
        assert result["Scope"] == 2
        assert result["Architecture"] == 1
        assert result["Total"] == 6
        assert result["Verdict"] == "APPROVE"

    def test_bold_criteria(self):
        text = """\
| Criterion | Score | Notes |
|-----------|-------|-------|
| **Feasibility** | 2/2 | good |
| **Testability** | 2/2 | ok |
| **Scope** | 1/2 | fine |
| **Architecture** | 1/2 | decent |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Total"] == 6

    def test_bare_digit_scores(self):
        text = """\
| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | 1 | notes |
| Testability | 1 | notes |
| Scope | 1 | notes |
| Architecture | 1 | notes |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Total"] == 4
        assert result["Verdict"] == "REVISE"

    def test_mixed_formats(self):
        text = """\
| Criterion | Score | Notes |
|-----------|-------|-------|
| **Feasibility** | 2/2 | good |
| Testability | 0 | bad |
| Scope | 1/2 | ok |
| **Architecture** | 2 | fine |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Feasibility"] == 2
        assert result["Testability"] == 0
        assert result["Scope"] == 1
        assert result["Architecture"] == 2
        assert result["Total"] == 5

    def test_missing_criterion_returns_none(self):
        text = """\
| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | 2/2 | good |
| Testability | 1/2 | ok |
| Scope | 2/2 | fine |
"""
        assert extract_scores(text) is None

    def test_data_not_found_error(self):
        text = """\
Data file not found.

| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | -/2 | N/A |
| Testability | -/2 | N/A |
| Scope | -/2 | N/A |
| Architecture | -/2 | N/A |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Verdict"] == "ERROR"
        assert result["Needs_Attention"] is True
        assert result["Total"] == 0

    def test_unable_to_assess_error(self):
        text = """\
Unable to assess strategy — file missing.

| Criterion | Score |
|-----------|-------|
| Feasibility | -/2 |
| Testability | -/2 |
| Scope | -/2 |
| Architecture | -/2 |
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Verdict"] == "ERROR"

    def test_non_table_lines_ignored(self):
        text = """\
Some preamble text here.

# Assessment Result

| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility | 2/2 | good |
| Testability | 2/2 | ok |
| Scope | 2/2 | fine |
| Architecture | 2/2 | decent |

Some trailing text.
"""
        result = extract_scores(text)
        assert result is not None
        assert result["Total"] == 8

    def test_only_first_match_per_criterion(self):
        text = """\
| Criterion | Score |
|-----------|-------|
| Feasibility | 2/2 |
| Testability | 1/2 |
| Scope | 1/2 |
| Architecture | 0/2 |
| Feasibility | 0/2 |
"""
        result = extract_scores(text)
        assert result["Feasibility"] == 2


# ---------------------------------------------------------------------------
# extract_title
# ---------------------------------------------------------------------------

class TestExtractTitle:
    def test_plain_title(self):
        assert extract_title("TITLE: My Strategy") == "My Strategy"

    def test_bold_title(self):
        assert extract_title("**TITLE**: Bold Strategy") == "Bold Strategy"

    def test_title_with_surrounding_text(self):
        text = "Some preamble\nTITLE: The Strategy\nMore text"
        assert extract_title(text) == "The Strategy"

    def test_no_title(self):
        assert extract_title("No title line here\nJust text") == ""

    def test_title_strips_whitespace(self):
        assert extract_title("TITLE:   Spaced Out  ") == "Spaced Out"


# ---------------------------------------------------------------------------
# CLI (subprocess)
# ---------------------------------------------------------------------------

class TestParseResultsCLI:
    def test_happy_path(self, tmp_path):
        make_result_file(tmp_path, "RHAISTRAT-1001", f=2, t=2, s=2, a=2)
        make_result_file(tmp_path, "RHAISTRAT-1002", f=1, t=1, s=1, a=1)
        make_result_file(tmp_path, "RHAISTRAT-1003", f=0, t=1, s=1, a=0)

        result = run_script("parse_results.py", [str(tmp_path)])
        assert result.returncode == 0

        csv_path = tmp_path / "scores.csv"
        assert csv_path.exists()

        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3
        assert rows[0]["ID"] == "RHAISTRAT-1001"
        assert rows[0]["Verdict"] == "APPROVE"
        assert rows[1]["Verdict"] == "REVISE"
        assert rows[2]["Verdict"] == "REJECT"

    def test_custom_output_path(self, tmp_path):
        make_result_file(tmp_path, "RHAISTRAT-2001", f=2, t=2, s=1, a=1)
        out = tmp_path / "custom.csv"

        result = run_script("parse_results.py", [str(tmp_path), "-o", str(out)])
        assert result.returncode == 0
        assert out.exists()

    def test_empty_dir_exits_1(self, tmp_path):
        result = run_script("parse_results.py", [str(tmp_path)])
        assert result.returncode == 1
        assert "No .result.md files" in result.stderr

    def test_unparseable_files_warned(self, tmp_path):
        make_result_file(tmp_path, "RHAISTRAT-3001", f=2, t=2, s=1, a=1)
        # Write a malformed result file
        bad = tmp_path / "RHAISTRAT-3002.result.md"
        bad.write_text("This is not a valid result file\n")

        result = run_script("parse_results.py", [str(tmp_path)])
        assert result.returncode == 0
        assert "Could not parse" in result.stderr

        with open(tmp_path / "scores.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
