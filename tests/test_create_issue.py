"""Integration tests for create_issue() against jira-emulator."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from jira_utils import create_issue


ADF_DESC = {
    "type": "doc",
    "version": 1,
    "content": [
        {"type": "paragraph",
         "content": [{"type": "text", "text": "Test description."}]}
    ],
}


class TestCreateIssue:

    def test_created_issue_has_no_assignee(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Unassigned issue",
            description_adf=ADF_DESC,
            priority="Major",
        )
        issue = jira.get(key)
        assignee = issue["fields"].get("assignee")
        assert assignee is None

    def test_summary_and_priority_round_trip(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Round-trip check",
            description_adf=ADF_DESC,
            priority="Critical",
        )
        issue = jira.get(key)
        assert issue["fields"]["summary"] == "Round-trip check"
        assert issue["fields"]["priority"]["name"] == "Critical"

    def test_labels_are_set(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Labeled issue",
            description_adf=ADF_DESC,
            priority="Major",
            labels=["alpha", "beta"],
        )
        issue = jira.get(key)
        assert sorted(issue["fields"].get("labels", [])) == ["alpha", "beta"]

    def test_components_are_set(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Component issue",
            description_adf=ADF_DESC,
            priority="Major",
            components=["Dashboard", "Notebooks"],
        )
        issue = jira.get(key)
        names = sorted(
            c["name"] for c in issue["fields"].get("components", []))
        assert names == ["Dashboard", "Notebooks"]

    def test_fix_and_affects_versions_are_set(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Versioned issue",
            description_adf=ADF_DESC,
            priority="Major",
            fix_versions=["2.12"],
            affects_versions=["2.10"],
        )
        issue = jira.get(key)
        fix_names = [v["name"] for v in issue["fields"].get("fixVersions", [])]
        assert "2.12" in fix_names
        aff_names = [v["name"] for v in issue["fields"].get("versions", [])]
        assert "2.10" in aff_names

    def test_parent_key_is_set(self, jira):
        parent_key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Epic",
            summary="Parent epic",
            description_adf=ADF_DESC,
            priority="Major",
        )
        child_key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Child task",
            description_adf=ADF_DESC,
            priority="Major",
            parent_key=parent_key,
        )
        child = jira.get(child_key)
        assert child["fields"]["parent"]["key"] == parent_key

    def test_minimal_call_only_required_args(self, jira):
        key = create_issue(
            jira.url, "admin", "admin",
            project="RHAISTRAT",
            issue_type="Feature",
            summary="Minimal issue",
            description_adf=ADF_DESC,
            priority="Major",
        )
        issue = jira.get(key)
        assert issue["key"] == key
        assert issue["fields"]["summary"] == "Minimal issue"
        assert issue["fields"].get("assignee") is None
