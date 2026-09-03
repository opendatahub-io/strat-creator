#!/usr/bin/env python3
"""Fetch a Jira issue and print selected fields as JSON.

Usage:
    python3 scripts/get_issue_json.py RHAISTRAT-2283 --fields project,status,labels,issuelinks,subtasks
    python3 scripts/get_issue_json.py RHAIRFE-1234 --fields status

Environment variables: JIRA_SERVER, JIRA_USER, JIRA_TOKEN
"""

import argparse
import json
import sys

from jira_utils import get_issue, require_env


def main():
    parser = argparse.ArgumentParser(description="Fetch Jira issue fields as JSON")
    parser.add_argument("key", help="Issue key (e.g. RHAISTRAT-2283)")
    parser.add_argument("--fields", required=True,
                        help="Comma-separated field names")
    args = parser.parse_args()

    server, user, token = require_env()
    fields = [f.strip() for f in args.fields.split(",")]
    data = get_issue(server, user, token, args.key, fields=fields)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
