---
name: export-rubric
description: Export the assess-strat scoring rubric to artifacts/strat-rubric.md in the current working directory.
allowed-tools: Read, Write, Bash
---

## Usage
```
/export-rubric
```

## Instructions

### Script Location

The rubric exporter is maintained in this repository at
`scripts/assess-strat/export_rubric.py`.

### Steps

1. Run `python3 scripts/assess-strat/export_rubric.py` from the current working directory.
2. Confirm the file was written and print its path.

### Required Permissions

Add to your user or project `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 scripts/assess-strat/export_rubric.py:*)"
    ]
  }
}
```
