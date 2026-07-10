"""Integration tests for clone_issue.py against jira-emulator."""
import json
import os
import subprocess
import sys

import pytest


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "clone_issue.py")


def _env(jira):
    return {
        **os.environ,
        "JIRA_SERVER": jira.url,
        "JIRA_USER": "admin",
        "JIRA_TOKEN": "admin",
    }


def _run(jira, args, env_override=None):
    env = env_override if env_override is not None else _env(jira)
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True, text=True, env=env,
    )


class TestCloneIssue:

    def test_clones_issue_with_summary_priority_and_link(self, jira):
        jira.create("RHAIRFE-1000", "GPU sharing for notebooks",
                     "Enable time-sliced GPU sharing.")

        result = _run(jira, ["RHAIRFE-1000", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        assert new_key.startswith("RHAISTRAT-"), f"unexpected key: {new_key}"

        clone = jira.get(new_key)
        assert clone["fields"]["summary"] == "GPU sharing for notebooks"

        source = jira.get("RHAIRFE-1000")
        source_priority = source["fields"].get("priority")
        clone_priority = clone["fields"].get("priority")
        if isinstance(source_priority, dict) and isinstance(clone_priority, dict):
            assert clone_priority["name"] == source_priority["name"]

        links = clone["fields"].get("issuelinks", [])
        cloner_links = [
            lk for lk in links
            if lk.get("type", {}).get("name") == "Cloners"
        ]
        assert len(cloner_links) >= 1
        linked_keys = []
        for lk in cloner_links:
            for direction in ("inwardIssue", "outwardIssue"):
                issue = lk.get(direction)
                if issue:
                    linked_keys.append(issue["key"])
        assert "RHAIRFE-1000" in linked_keys

    def test_clone_link_direction_strategy_is_outward(self, jira):
        """The strategy must be the outward (cloning) side of the link."""
        jira.create("RHAIRFE-1010", "Direction test RFE",
                     "Verify clone link direction.")

        result = _run(jira, ["RHAIRFE-1010", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        strat_key = result.stdout.strip()

        # The emulator's GET response uses the key name to indicate which
        # DB column the current issue occupies: "outwardIssue" means the
        # current issue is outward_issue_id, "inwardIssue" means inward.
        strat = jira.get(strat_key)
        strat_links = [
            lk for lk in strat["fields"].get("issuelinks", [])
            if lk.get("type", {}).get("name") == "Cloners"
        ]
        assert len(strat_links) == 1
        lk = strat_links[0]
        assert "outwardIssue" in lk, (
            "strategy should be the outward side (clones the RFE)")

        rfe = jira.get("RHAIRFE-1010")
        rfe_links = [
            lk for lk in rfe["fields"].get("issuelinks", [])
            if lk.get("type", {}).get("name") == "Cloners"
        ]
        assert len(rfe_links) == 1
        lk = rfe_links[0]
        assert "inwardIssue" in lk, (
            "RFE should be the inward side (is cloned by the strategy)")

    def test_labels_are_copied_to_clone(self, jira):
        jira.create("RHAIRFE-1001", "Model serving autoscaler",
                     "Autoscale model serving pods.",
                     labels=["strat-creator-3.5", "tech-reviewed"])

        result = _run(jira, ["RHAIRFE-1001", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        clone_labels = clone["fields"].get("labels", [])
        assert "strat-creator-3.5" in clone_labels
        assert "tech-reviewed" in clone_labels

    def test_components_fix_versions_affects_versions_are_copied(self, jira):
        jira.create("RHAIRFE-1002", "Pipeline orchestration",
                     "Orchestrate ML pipelines.",
                     components=["Dashboard", "Model Registry"],
                     fix_versions=["2.12", "2.13"],
                     affects_versions=["2.10"])

        result = _run(jira, ["RHAIRFE-1002", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        clone_fields = clone["fields"]

        comp_names = sorted(c["name"] for c in clone_fields.get("components", []))
        assert comp_names == ["Dashboard", "Model Registry"]

        fix_names = sorted(v["name"] for v in clone_fields.get("fixVersions", []))
        assert fix_names == ["2.12", "2.13"]

        aff_names = [v["name"] for v in clone_fields.get("versions", [])]
        assert aff_names == ["2.10"]

    def test_clone_inherits_parent_outcome_from_rfe(self, jira):
        jira.create("RHAISTRAT-500", "AI Hub Delivery",
                     "Top-level Outcome.", issue_type="Outcome")
        jira.create("RHAIRFE-1003", "Agent catalog search",
                     "Search for agents in the catalog.",
                     parent_key="RHAISTRAT-500")

        result = _run(jira, ["RHAIRFE-1003", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        assert clone["fields"]["parent"]["key"] == "RHAISTRAT-500"
        assert "Setting parent Outcome: RHAISTRAT-500" in result.stderr

    def test_clone_skips_closed_parent_outcome(self, jira):
        jira.create("RHAISTRAT-501", "Old Outcome",
                     "Deprecated.", issue_type="Outcome", status="Closed")
        jira.create("RHAIRFE-1004", "Legacy feature",
                     "Should not inherit closed parent.",
                     parent_key="RHAISTRAT-501")

        result = _run(jira, ["RHAIRFE-1004", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        assert clone["fields"].get("parent") is None
        assert "Closed" in result.stderr

    def test_clone_no_parent_on_rfe(self, jira):
        jira.create("RHAIRFE-1005", "Standalone feature",
                     "No parent Outcome on the RFE.")

        result = _run(jira, ["RHAIRFE-1005", "--target-project", "RHAISTRAT"])
        assert result.returncode == 0, f"stderr: {result.stderr}"

        new_key = result.stdout.strip()
        clone = jira.get(new_key)
        assert clone["fields"].get("parent") is None
        assert "No parent Outcome found" in result.stderr

    def test_missing_env_vars_exits_with_code_2(self, jira):
        env = {k: v for k, v in os.environ.items()
               if k not in ("JIRA_SERVER", "JIRA_USER", "JIRA_TOKEN")}

        result = _run(jira, ["RHAIRFE-1000", "--target-project", "RHAISTRAT"],
                       env_override=env)
        assert result.returncode == 2
