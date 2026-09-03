---
name: strategy-reject
description: Reject a pipeline-created strategy, close it in Jira, and return its source RFE for human rework.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

Reject a RHAISTRAT only when an SME has determined that its source RFE needs
rework. This is a Jira-writing workflow. Do not modify strategy content,
close child epics, or remove the RFE rework label; the RFE owner performs the
rework and explicitly removes that label when ready.

## Input

$ARGUMENTS must contain exactly one RHAISTRAT key, for example RHAISTRAT-2283.
If it is missing or does not match RHAISTRAT-NNNN, stop with:

~~~
Usage: /strategy-reject RHAISTRAT-NNNN
~~~

## State and credentials

This workflow persists progress so it can resume safely after context
compression. Set these paths after validating the key:

~~~bash
STATE_FILE="tmp/strategy-reject-RHAISTRAT-NNNN.state"
REASON_FILE="tmp/strategy-reject-RHAISTRAT-NNNN-reason.md"
~~~

All Jira operations require JIRA_SERVER, JIRA_USER, and JIRA_TOKEN. Use
require_env() from jira_utils.py; if any are absent, report the missing
credentials and stop before making changes.

If STATE_FILE already exists, read it with state.py and resume at its recorded
phase. Always refetch the STRAT before resuming. Do not repeat a completed
comment, transition, or label operation merely because the skill was
re-entered.

## Step 1: Validate the STRAT

Fetch the STRAT with its project, status, labels, issue links, and subtasks:

~~~bash
python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import get_issue, require_env
s, u, t = require_env()
data = get_issue(s, u, t, sys.argv[1],
                 fields=['project', 'status', 'labels', 'issuelinks', 'subtasks'])
print(json.dumps(data, indent=2))
" RHAISTRAT-NNNN
~~~

Stop and report an error if any of these checks fail:

1. The issue exists and fields.project.key is RHAISTRAT.
2. The labels include strat-creator-auto-created.

Set strat_terminal=true when fields.status.statusCategory.key is done. An
already Closed or Resolved STRAT is not a validation failure: it is a
reconciliation case, so its rejection comment and RFE updates still run but
its Jira transition is skipped.

## Step 2: Resolve the source RFE and warn about child epics

From fields.issuelinks, inspect only links whose type name is Cloners. For
each such link, inspect both outwardIssue and inwardIssue; the source RFE is
the first linked key beginning RHAIRFE-. If there is no such key, report
RHAISTRAT-NNNN has no Cloners link to an RHAIRFE and stop.

Find child Epics through the parent hierarchy, then include any RHAISTRAT
subtasks as a fallback. Do not rely on a fixed key suffix:

~~~bash
python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import require_env, search_issues
s, u, t = require_env()
issues = search_issues(s, u, t,
                       'parent = ' + sys.argv[1] + ' AND project = RHAISTRAT',
                       fields=['key', 'issuetype'])
epics = [issue['key'] for issue in issues
         if issue.get('fields', {}).get('issuetype', {}).get('name') == 'Epic']
print(json.dumps(epics))
" RHAISTRAT-NNNN
~~~

If any child epics exist, warn before proceeding:

~~~
WARNING: RHAISTRAT-NNNN has N child epic(s): RHAISTRAT-NNNN-1, ...
These epics will NOT be automatically closed. You may need to close them
manually or use /epic-rewind (future skill) to unwind them.
~~~

Initialize the state only after validation and RFE resolution succeed:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py init "$STATE_FILE" \
  "strat_key=RHAISTRAT-NNNN" "rfe_key=RHAIRFE-MMMM" \
  "strat_terminal=true-or-false" "phase=validated"
~~~

## Step 3: Collect the rejection reason

Ask the SME for a rejection comment before making Jira changes. It must say
why the STRAT is rejected and what the RFE must change before a fresh STRAT
can be created. Do not accept an empty reason.

Save the exact response in REASON_FILE with the Write tool, then persist the
phase:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" \
  "phase=reason-collected"
~~~

## Step 4: Comment on and close the STRAT

First add this exact semantic content to the STRAT. Use markdown_to_adf() and
a Markdown level-three heading so Jira receives an ADF heading equivalent to
h3. Strategy rejected:

~~~markdown
### Strategy rejected

{rejection reason from SME}

This strategy has been closed. The source RFE (RHAIRFE-MMMM) has been
returned for rework.
~~~

Post it with add_comment():

~~~bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_comment, markdown_to_adf, require_env
s, u, t = require_env()
reason_path, strat_key, rfe_key = sys.argv[1:]
body = '\n\n'.join([
    '### Strategy rejected',
    Path(reason_path).read_text().strip(),
    f'This strategy has been closed. The source RFE ({rfe_key}) has been returned for rework.',
]) + '\n'
add_comment(s, u, t, strat_key, markdown_to_adf(body))
" "$REASON_FILE" RHAISTRAT-NNNN RHAIRFE-MMMM
~~~

Record phase=strat-commented only after the comment succeeds:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" \
  "phase=strat-commented"
~~~

If strat_terminal=true, skip only the transition and record
phase=strat-closed:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" \
  "phase=strat-closed"
~~~

Otherwise, fetch and display every available transition:

~~~bash
python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import get_transitions, require_env
s, u, t = require_env()
print(json.dumps(get_transitions(s, u, t, sys.argv[1]), indent=2))
" RHAISTRAT-NNNN
~~~

Find a transition whose destination status (to.name) is Closed. Select Won't
Do as its resolution when that resolution is available; otherwise use Rejected
when available. Inspect the selected transition's resolution allowedValues
when Jira supplies them. If Jira does not supply allowedValues, try Won't Do;
only if Jira rejects that resolution may you retry the same Closed transition
with Rejected. Execute only that transition using do_transition() with a
resolution field:

~~~bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import do_transition, require_env
s, u, t = require_env()
do_transition(s, u, t, sys.argv[1], sys.argv[2],
              fields={'resolution': {'name': sys.argv[3]}})
" RHAISTRAT-NNNN TRANSITION_ID "Won't Do"
~~~

If there is no transition to Closed, a usable resolution cannot be selected,
or the transition fails, report the available transitions and stop. Do not
choose another workflow transition or update the RFE. Record
phase=strat-closed only after the transition succeeds:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" \
  "phase=strat-closed"
~~~

## Step 5: Update the source RFE

Fetch the RFE status. If fields.status.statusCategory.key is done, warn the
SME that the RFE is already closed, but continue. The human must reopen it or
create a new RFE; this skill does neither.

~~~bash
python3 -c "
import json, sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import get_issue, require_env
s, u, t = require_env()
print(json.dumps(get_issue(s, u, t, sys.argv[1], fields=['status']), indent=2))
" RHAIRFE-MMMM
~~~

Add this ADF-formatted comment to the RFE using add_comment() and
markdown_to_adf():

~~~markdown
### Strategy rejected — rework needed

The strategy RHAISTRAT-NNNN has been rejected for the following reason:

{rejection reason from SME}

Please review and update this RFE. When ready, remove the
strat-creator-rework-needed label to allow a new strategy to be created.
~~~

Post it, then record phase=rfe-commented after the comment succeeds:

~~~bash
python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_comment, markdown_to_adf, require_env
s, u, t = require_env()
reason_path, strat_key, rfe_key = sys.argv[1:]
body = '\n\n'.join([
    '### Strategy rejected — rework needed',
    f'The strategy {strat_key} has been rejected for the following reason:',
    Path(reason_path).read_text().strip(),
    'Please review and update this RFE. When ready, remove the strat-creator-rework-needed label to allow a new strategy to be created.',
]) + '\n'
add_comment(s, u, t, rfe_key, markdown_to_adf(body))
" "$REASON_FILE" RHAISTRAT-NNNN RHAIRFE-MMMM

python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" \
  "phase=rfe-commented"
~~~

Then perform the label updates in this order. Both calls are intentionally
idempotent:

~~~bash
python3 -c "
import sys
sys.path.insert(0, '${CLAUDE_SKILL_DIR}/scripts')
from jira_utils import add_labels, remove_labels, require_env
s, u, t = require_env()
rfe_key = sys.argv[1]
remove_labels(s, u, t, rfe_key, ['strat-creator-consumed'])
add_labels(s, u, t, rfe_key, ['strat-creator-rework-needed'])
" RHAIRFE-MMMM
~~~

Record phase=complete only after both label calls succeed. If
strat-creator-consumed is absent, its removal is a no-op and is not an error:

~~~bash
python3 ${CLAUDE_SKILL_DIR}/scripts/state.py set "$STATE_FILE" "phase=complete"
~~~

## Step 6: Report

Print this summary, using the STRAT final existing status if it was already
terminal:

~~~
Strategy rejected:
  STRAT:  RHAISTRAT-NNNN → Closed
  RFE:    RHAIRFE-MMMM   → strat-creator-rework-needed

The RFE is now on hold. To resume:
  1. Update the RFE or leave a comment with new context
  2. Remove the strat-creator-rework-needed label
  3. The strat-pipeline will create a fresh strategy on its next run
~~~

$ARGUMENTS
