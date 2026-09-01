"""Tests for check_progress.py — progress reporting."""

from conftest import parse_kv_output, run_script


class TestCheckProgress:
    def test_partial_progress(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Create strat dir with 10 files
        strat_dir = tmp_path / "strats"
        strat_dir.mkdir()
        for i in range(1, 11):
            (strat_dir / f"RHAISTRAT-{i}.md").write_text("strategy")

        # Record strat_dir in run
        (run_dir / "strat_dir.txt").write_text(str(strat_dir) + "\n")

        # Simulate 5 completed results
        for i in range(1, 6):
            (run_dir / f"RHAISTRAT-{i}.result.md").write_text("result")

        result = run_script("check_progress.py", [str(run_dir)])
        assert result.returncode == 0

        kv = parse_kv_output(result.stdout)
        assert int(kv["COMPLETED"]) == 5
        assert int(kv["TOTAL"]) == 10
        assert int(kv["REMAINING"]) == 5

    def test_all_complete(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        strat_dir = tmp_path / "strats"
        strat_dir.mkdir()
        for i in range(1, 4):
            (strat_dir / f"RHAISTRAT-{i}.md").write_text("strategy")
            (run_dir / f"RHAISTRAT-{i}.result.md").write_text("result")

        (run_dir / "strat_dir.txt").write_text(str(strat_dir) + "\n")

        result = run_script("check_progress.py", [str(run_dir)])
        kv = parse_kv_output(result.stdout)
        assert int(kv["COMPLETED"]) == 3
        assert int(kv["TOTAL"]) == 3
        assert int(kv["REMAINING"]) == 0

    def test_no_strat_dir_file(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "RHAISTRAT-1.result.md").write_text("result")

        result = run_script("check_progress.py", [str(run_dir)])
        kv = parse_kv_output(result.stdout)
        assert int(kv["COMPLETED"]) == 1
        assert int(kv["TOTAL"]) == 0
        assert int(kv["REMAINING"]) == 0

    def test_missing_run_dir(self, tmp_path):
        result = run_script("check_progress.py", [str(tmp_path / "nonexistent")])
        assert result.returncode == 1

    def test_no_args_exits_1(self):
        result = run_script("check_progress.py", [])
        assert result.returncode == 1

    def test_filters_review_files_from_total(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        strat_dir = tmp_path / "strats"
        strat_dir.mkdir()
        (strat_dir / "RHAISTRAT-1.md").write_text("strategy")
        (strat_dir / "RHAISTRAT-1-review.md").write_text("review")

        (run_dir / "strat_dir.txt").write_text(str(strat_dir) + "\n")

        result = run_script("check_progress.py", [str(run_dir)])
        kv = parse_kv_output(result.stdout)
        assert int(kv["TOTAL"]) == 1
