"""Shared test fixtures for assess-strat tests."""
import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "assess-strat")


def run_script(script_name, args, cwd=None):
    """Run a script from the scripts/ directory as a subprocess."""
    script = os.path.join(os.path.abspath(SCRIPTS_DIR), script_name)
    result = subprocess.run(
        [sys.executable, script] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result


def parse_kv_output(stdout):
    """Parse KEY=VALUE output lines into a dict."""
    kv = {}
    for line in stdout.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            kv[key] = value
    return kv


@pytest.fixture
def scripts_dir():
    """Return the absolute path to the scripts/ directory."""
    return os.path.abspath(SCRIPTS_DIR)


@pytest.fixture
def strat_dir(tmp_path):
    """Create a temp directory with sample strategy .md stubs."""
    d = tmp_path / "strategies"
    d.mkdir()
    for i in range(1, 6):
        (d / f"RHAISTRAT-{1000 + i}.md").write_text(
            f"---\nstrat_id: RHAISTRAT-{1000 + i}\n---\n\n# Strategy {i}\n"
        )
    # Add a review file that should be excluded
    (d / "RHAISTRAT-1001-review.md").write_text("review content")
    return d


SAMPLE_RESULT = """\
TITLE: {title}

| Criterion | Score | Notes |
|-----------|-------|-------|
| Feasibility     | {f}/2 | feasibility notes |
| Testability     | {t}/2 | testability notes |
| Scope           | {s}/2 | scope notes |
| Architecture    | {a}/2 | architecture notes |
| **Total**       | **{total}/8** | |

### Verdict: {verdict}
### Needs Attention: {needs_attention}
"""


def make_result_file(path, key, f=2, t=2, s=1, a=1):
    """Write a sample .result.md file with given scores."""
    total = f + t + s + a
    zero_count = sum(1 for x in [f, t, s, a] if x == 0)
    if total >= 6 and zero_count == 0:
        verdict = "APPROVE"
    elif total < 3 or zero_count >= 2:
        verdict = "REJECT"
    else:
        verdict = "REVISE"
    needs_attention = verdict != "APPROVE"

    content = SAMPLE_RESULT.format(
        title=f"Strategy for {key}",
        f=f, t=t, s=s, a=a,
        total=total,
        verdict=verdict,
        needs_attention=str(needs_attention).lower(),
    )
    filepath = os.path.join(str(path), f"{key}.result.md")
    with open(filepath, "w") as fh:
        fh.write(content)
    return filepath


@pytest.fixture
def run_dir(tmp_path):
    """Create a temp run directory with sample result files."""
    d = tmp_path / "run"
    d.mkdir()
    make_result_file(d, "RHAISTRAT-1001", f=2, t=2, s=2, a=2)  # APPROVE (8)
    make_result_file(d, "RHAISTRAT-1002", f=1, t=1, s=1, a=1)  # REVISE (4)
    make_result_file(d, "RHAISTRAT-1003", f=0, t=0, s=1, a=1)  # REJECT (2)
    return d


@pytest.fixture
def scores_csv(run_dir, scripts_dir):
    """Generate a scores.csv from the run_dir result files."""
    result = run_script("parse_results.py", [str(run_dir)])
    assert result.returncode == 0, result.stderr
    return os.path.join(str(run_dir), "scores.csv")
