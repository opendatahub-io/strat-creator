"""Tests for preflight.py — strategy directory and run state validation."""
import os

from conftest import parse_kv_output, run_script


class TestPreflight:
    def test_valid_strat_dir(self, strat_dir, tmp_path):
        result = run_script("preflight.py", [str(strat_dir)], cwd=str(tmp_path))
        assert result.returncode == 0

        kv = parse_kv_output(result.stdout)
        assert kv["STRAT_DIR_EXISTS"] == "true"
        assert int(kv["STRAT_COUNT"]) == 5

    def test_missing_strat_dir(self, tmp_path):
        result = run_script("preflight.py", [str(tmp_path / "nope")], cwd=str(tmp_path))
        assert result.returncode == 0

        kv = parse_kv_output(result.stdout)
        assert kv["STRAT_DIR_EXISTS"] == "false"
        assert int(kv["STRAT_COUNT"]) == 0

    def test_filters_review_files(self, strat_dir, tmp_path):
        result = run_script("preflight.py", [str(strat_dir)], cwd=str(tmp_path))
        kv = parse_kv_output(result.stdout)
        # 5 strategy files, 1 review file → count should be 5
        assert int(kv["STRAT_COUNT"]) == 5

    def test_no_current_run(self, strat_dir, tmp_path):
        result = run_script("preflight.py", [str(strat_dir)], cwd=str(tmp_path))
        kv = parse_kv_output(result.stdout)
        assert kv["CURRENT_RUN"] == "none"

    def test_with_current_run(self, strat_dir, tmp_path):
        # Set up assessments/current → a run dir
        assess_dir = tmp_path / "assessments"
        assess_dir.mkdir()
        run_dir = assess_dir / "20260101-120000"
        run_dir.mkdir()

        # Add some result files
        (run_dir / "RHAISTRAT-1001.result.md").write_text("result")
        (run_dir / "RHAISTRAT-1002.result.md").write_text("result")

        os.symlink("20260101-120000", str(assess_dir / "current"))

        result = run_script("preflight.py", [str(strat_dir)], cwd=str(tmp_path))
        kv = parse_kv_output(result.stdout)
        assert "CURRENT_RUN" in kv
        assert kv["CURRENT_RUN"] != "none"
        assert int(kv["CURRENT_ASSESSED"]) == 2
        assert kv["CURRENT_COMPLETE"] == "false"

    def test_complete_current_run(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        assess_dir.mkdir()
        run_dir = assess_dir / "20260101-120000"
        run_dir.mkdir()
        (run_dir / "scores.csv").write_text("ID,Total\n")
        os.symlink("20260101-120000", str(assess_dir / "current"))

        result = run_script("preflight.py", [str(strat_dir)], cwd=str(tmp_path))
        kv = parse_kv_output(result.stdout)
        assert kv["CURRENT_COMPLETE"] == "true"

    def test_no_args_exits_1(self):
        result = run_script("preflight.py", [])
        assert result.returncode == 1
