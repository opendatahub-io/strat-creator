"""Tests for setup_run.py — run directory creation, resume, queue management."""
import os

from conftest import parse_kv_output, run_script


class TestSetupRunNewRun:
    def test_creates_run_dir_and_queue(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        result = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        assert result.returncode == 0

        kv = parse_kv_output(result.stdout)
        assert kv["RESUMING"] == "false"
        assert int(kv["PENDING"]) == 5
        assert int(kv["TOTAL_STRATEGIES"]) == 5
        assert int(kv["ALREADY_ASSESSED"]) == 0

        run_dir = kv["RUN_DIR"]
        assert os.path.isdir(run_dir)
        assert os.path.exists(os.path.join(run_dir, "queue.txt"))
        assert os.path.exists(os.path.join(run_dir, "strat_dir.txt"))

        # Current symlink created
        current = os.path.join(str(assess_dir), "current")
        assert os.path.islink(current)

    def test_queue_contains_all_keys(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        result = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv = parse_kv_output(result.stdout)
        queue_file = kv["QUEUE_FILE"]

        with open(queue_file) as f:
            keys = [line.strip() for line in f if line.strip()]
        assert len(keys) == 5
        assert all(k.startswith("RHAISTRAT-") for k in keys)

    def test_filters_review_files(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        result = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv = parse_kv_output(result.stdout)
        # strat_dir fixture has 5 .md files + 1 -review.md → should be 5
        assert int(kv["TOTAL_STRATEGIES"]) == 5

    def test_limit_flag(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        result = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir), "--limit", "2",
        ])
        kv = parse_kv_output(result.stdout)
        assert int(kv["PENDING"]) == 2

        with open(kv["QUEUE_FILE"]) as f:
            keys = [line.strip() for line in f if line.strip()]
        assert len(keys) == 2

    def test_strat_dir_recorded(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        result = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv = parse_kv_output(result.stdout)
        strat_dir_file = os.path.join(kv["RUN_DIR"], "strat_dir.txt")
        with open(strat_dir_file) as f:
            recorded = f.read().strip()
        assert recorded == os.path.abspath(str(strat_dir))


class TestSetupRunResume:
    def test_resumes_incomplete_run(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"
        # First run
        r1 = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv1 = parse_kv_output(r1.stdout)
        run_dir_1 = kv1["RUN_DIR"]

        # Simulate 2 assessed strategies
        for key in ["RHAISTRAT-1001", "RHAISTRAT-1002"]:
            with open(os.path.join(run_dir_1, f"{key}.result.md"), "w") as f:
                f.write("dummy result\n")

        # Second run should resume
        r2 = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv2 = parse_kv_output(r2.stdout)
        assert kv2["RESUMING"] == "true"
        assert kv2["RUN_DIR"] == run_dir_1
        assert int(kv2["ALREADY_ASSESSED"]) == 2
        assert int(kv2["PENDING"]) == 3

    def test_new_run_after_complete(self, strat_dir, tmp_path):
        assess_dir = tmp_path / "assessments"

        # Create a pre-existing completed run dir manually
        old_run = assess_dir / "20250101-120000"
        old_run.mkdir(parents=True)
        (old_run / "scores.csv").write_text("ID,Total\n")
        os.symlink("20250101-120000", str(assess_dir / "current"))

        r2 = run_script("setup_run.py", [
            str(strat_dir), "--assess-dir", str(assess_dir),
        ])
        kv2 = parse_kv_output(r2.stdout)
        assert kv2["RESUMING"] == "false"
        assert kv2["RUN_DIR"] != str(old_run)


class TestSetupRunErrors:
    def test_missing_strat_dir(self, tmp_path):
        result = run_script("setup_run.py", [
            str(tmp_path / "nonexistent"),
            "--assess-dir", str(tmp_path / "assessments"),
        ])
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_empty_strat_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = run_script("setup_run.py", [
            str(empty), "--assess-dir", str(tmp_path / "assessments"),
        ])
        assert result.returncode == 1
        assert "No strategy files" in result.stderr
