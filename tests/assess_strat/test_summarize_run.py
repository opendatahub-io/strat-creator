"""Tests for summarize_run.py — score loading, summary statistics, CLI."""
import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "assess-strat"))
from conftest import run_script
from summarize_run import CRITERIA, load_scores, summarize


def _write_scores_csv(path, rows):
    """Write a scores.csv file with the given row dicts."""
    fieldnames = ["ID", "Title"] + CRITERIA + ["Total", "Verdict", "Needs_Attention"]
    with open(os.path.join(str(path), "scores.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(key, f, t, s, a, verdict, needs=True):
    return {
        "ID": key, "Title": f"Strategy {key}",
        "Feasibility": f, "Testability": t, "Scope": s, "Architecture": a,
        "Total": f + t + s + a, "Verdict": verdict,
        "Needs_Attention": str(needs),
    }


# ---------------------------------------------------------------------------
# load_scores
# ---------------------------------------------------------------------------

class TestLoadScores:
    def test_load_from_csv_file(self, tmp_path):
        _write_scores_csv(tmp_path, [_row("S-1", 2, 2, 2, 2, "APPROVE", False)])
        rows = load_scores(str(tmp_path / "scores.csv"))
        assert len(rows) == 1
        assert rows[0]["Total"] == 8

    def test_load_from_directory(self, tmp_path):
        _write_scores_csv(tmp_path, [_row("S-1", 1, 1, 1, 1, "REVISE")])
        rows = load_scores(str(tmp_path))
        assert len(rows) == 1

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_scores(str(tmp_path / "nonexistent.csv"))


# ---------------------------------------------------------------------------
# summarize (capture stdout)
# ---------------------------------------------------------------------------

class TestSummarize:
    def test_empty_rows(self, capsys):
        summarize([])
        assert "No results" in capsys.readouterr().out

    def test_all_approve(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "A", "Feasibility": 2, "Testability": 2,
             "Scope": 2, "Architecture": 2, "Total": 8, "Verdict": "APPROVE",
             "Needs_Attention": "False"},
            {"ID": "S-2", "Title": "B", "Feasibility": 2, "Testability": 2,
             "Scope": 1, "Architecture": 1, "Total": 6, "Verdict": "APPROVE",
             "Needs_Attention": "False"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "100.0%" in out
        assert "Approve:** 2" in out

    def test_mixed_verdicts(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "A", "Feasibility": 2, "Testability": 2,
             "Scope": 2, "Architecture": 2, "Total": 8, "Verdict": "APPROVE",
             "Needs_Attention": "False"},
            {"ID": "S-2", "Title": "B", "Feasibility": 1, "Testability": 1,
             "Scope": 1, "Architecture": 1, "Total": 4, "Verdict": "REVISE",
             "Needs_Attention": "True"},
            {"ID": "S-3", "Title": "C", "Feasibility": 0, "Testability": 0,
             "Scope": 1, "Architecture": 0, "Total": 1, "Verdict": "REJECT",
             "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "Approve:** 1" in out
        assert "Revise:** 1" in out
        assert "Reject:** 1" in out

    def test_errors_excluded_from_averages(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "A", "Feasibility": 2, "Testability": 2,
             "Scope": 2, "Architecture": 2, "Total": 8, "Verdict": "APPROVE",
             "Needs_Attention": "False"},
            {"ID": "S-2", "Title": "B", "Feasibility": 0, "Testability": 0,
             "Scope": 0, "Architecture": 0, "Total": 0, "Verdict": "ERROR",
             "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "Total assessed:** 1" in out
        assert "Errors (data not found):** 1" in out

    def test_zero_counts(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "A", "Feasibility": 0, "Testability": 2,
             "Scope": 2, "Architecture": 2, "Total": 6, "Verdict": "REVISE",
             "Needs_Attention": "True"},
            {"ID": "S-2", "Title": "B", "Feasibility": 0, "Testability": 1,
             "Scope": 1, "Architecture": 1, "Total": 3, "Verdict": "REVISE",
             "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "Feasib" in out

    def test_near_miss_detected(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "Almost There Strategy", "Feasibility": 2,
             "Testability": 1, "Scope": 1, "Architecture": 1, "Total": 5,
             "Verdict": "REVISE", "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "Near-Miss" in out
        assert "S-1" in out

    def test_near_miss_with_one_zero(self, capsys):
        rows = [
            {"ID": "S-1", "Title": "Close But Zero", "Feasibility": 0,
             "Testability": 2, "Scope": 2, "Architecture": 1, "Total": 5,
             "Verdict": "REVISE", "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "Near-Miss" in out
        assert "Feasibility" in out

    def test_what_if_analysis(self, capsys):
        # S-1: total=5, Feasibility=0, others nonzero. If Feasibility 0→1 → total=6, no zeros → APPROVE
        rows = [
            {"ID": "S-1", "Title": "Fixable", "Feasibility": 0,
             "Testability": 2, "Scope": 2, "Architecture": 1, "Total": 5,
             "Verdict": "REVISE", "Needs_Attention": "True"},
        ]
        summarize(rows)
        out = capsys.readouterr().out
        assert "What-If" in out
        assert "Feasibility" in out


# ---------------------------------------------------------------------------
# CLI (subprocess)
# ---------------------------------------------------------------------------

class TestSummarizeRunCLI:
    def test_run_against_directory(self, scores_csv):
        run_dir = os.path.dirname(scores_csv)
        result = run_script("summarize_run.py", [run_dir])
        assert result.returncode == 0
        assert "Assessment Summary" in result.stdout
        assert "Score Distribution" in result.stdout

    def test_run_against_csv_file(self, scores_csv):
        result = run_script("summarize_run.py", [scores_csv])
        assert result.returncode == 0
        assert "Assessment Summary" in result.stdout
