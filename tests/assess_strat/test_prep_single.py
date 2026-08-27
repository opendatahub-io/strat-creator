"""Tests for prep_single.py — stale result file cleanup."""
from conftest import run_script


class TestPrepSingle:
    def test_removes_existing_result(self, tmp_path):
        single_dir = tmp_path / "single"
        single_dir.mkdir()
        result_file = single_dir / "RHAISTRAT-1234.result.md"
        result_file.write_text("old result")

        result = run_script(
            "prep_single.py", ["RHAISTRAT-1234", "--single-dir", str(single_dir)]
        )
        assert result.returncode == 0
        assert f"REMOVED={result_file}" in result.stdout
        assert f"SINGLE_DIR={single_dir}" in result.stdout
        assert not result_file.exists()

    def test_no_existing_file(self, tmp_path):
        single_dir = tmp_path / "single"
        result = run_script(
            "prep_single.py", ["RHAISTRAT-9999", "--single-dir", str(single_dir)]
        )
        assert result.returncode == 0
        assert f"SINGLE_DIR={single_dir}" in result.stdout
        assert "REMOVED=" not in result.stdout

    def test_creates_single_dir(self, tmp_path):
        single_dir = tmp_path / "single"
        result = run_script(
            "prep_single.py", ["RHAISTRAT-5555", "--single-dir", str(single_dir)]
        )
        assert result.returncode == 0
        assert single_dir.is_dir()

    def test_no_args_exits_1(self):
        result = run_script("prep_single.py", [])
        assert result.returncode == 1
