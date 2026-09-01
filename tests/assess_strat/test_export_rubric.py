"""Tests for export_rubric.py — rubric extraction and export."""

from conftest import run_script


class TestExportRubric:
    def test_produces_rubric_file(self, tmp_path):
        result = run_script("export_rubric.py", [], cwd=str(tmp_path))
        assert result.returncode == 0

        rubric = tmp_path / "artifacts" / "strat-rubric.md"
        assert rubric.exists()

        content = rubric.read_text()
        assert content.startswith("# Strategy Assessment Rubric")
        assert "Scoring Rubric" in content

    def test_rubric_contains_criteria(self, tmp_path):
        run_script("export_rubric.py", [], cwd=str(tmp_path))
        content = (tmp_path / "artifacts" / "strat-rubric.md").read_text()

        assert "Feasibility" in content
        assert "Testability" in content
        assert "Scope" in content
        assert "Architecture" in content

    def test_rubric_has_source_notice(self, tmp_path):
        run_script("export_rubric.py", [], cwd=str(tmp_path))
        content = (tmp_path / "artifacts" / "strat-rubric.md").read_text()
        assert "read-only reference copy" in content

    def test_creates_artifacts_dir(self, tmp_path):
        assert not (tmp_path / "artifacts").exists()
        run_script("export_rubric.py", [], cwd=str(tmp_path))
        assert (tmp_path / "artifacts").is_dir()
