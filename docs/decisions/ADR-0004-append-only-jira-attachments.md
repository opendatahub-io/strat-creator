# ADR-0004: Treat Strat-Creator Jira Attachments as Append-Only

## Status

Proposed

## Context

https://redhat.atlassian.net/browse/RHAIFIRST-542
https://redhat.atlassian.net/browse/RHAIFIRST-437

`strat-creator` uses Jira attachments for strategy and review artifacts when
the Jira description cannot contain the complete document.
`scripts/push_strategy.py` currently attempts to delete an earlier attachment
before uploading a replacement and also deletes an attachment when a revised
strategy fits in the description again.

The CI service account does not have Jira attachment-delete permission. The
overflow path therefore uploads a new copy after a handled `403`, while the
orphan-cleanup path can fail after the description update has already
succeeded. This makes a successfully pushed strategy appear to have failed.

More importantly, the local SME-input flow is intentionally run by individual
humans using their personal Jira credentials. An SME may need to update a
strategy whose earlier attachment was created by CI or by another SME. Making
deletion reliable would require granting every SME broad permission to delete
attachments created by other users across the project. That is not an
appropriate or scalable permission model, so attachment deletion cannot be a
long-term correctness requirement even if the CI bot's permissions are fixed.

Because attachment deletion is unavailable and singular filenames are reused,
readers must also account for duplicate and orphaned attachments. The
description and attachment readers currently rely on attachment presence or
list order, which can return stale or nondeterministic content.

## Decision

Jira attachments managed by `strat-creator` are append-only. The pipeline will
not delete existing attachments as part of a strategy or review update.

This is driven by the credential and ownership model, not only by the current
CI `403`: both automated jobs and human SME flows must remain correct without
assuming that the actor has permission to delete another actor's attachment.

The readers establish the following authority and selection rules:

1. A strategy attachment is used only when the Jira description contains the
   attachment notice indicating that the full strategy exceeds the description
   size limit. If that marker is absent, the description is authoritative and
   any matching attachment is treated as an orphan.
2. When multiple strategy or review attachments have the same filename, the
   attachment with the newest Jira `created` timestamp is selected. If the
   timestamps are equal, numeric Jira `id` values take precedence and are
   compared numerically; if both IDs are nonnumeric, they are compared
   lexicographically. The `content` URL is the final lexicographic
   tie-breaker. This same ordering key is used by every attachment reader and
   selector.
3. `fetch_issue.py` deduplicates text attachments by filename and downloads
   only the newest copy.
4. `delete_attachment()` is no longer used by the pipeline and is documented
   as deprecated because the CI service account cannot perform the operation.
5. `_push_via_attachment()` serializes writers per RHAISTRAT issue with a
   per-issue process/thread lock backed by an OS advisory lock. The lock is
   held from before the upload through the description update, so an upload
   and its marker cannot interleave with another local writer. Callers on
   separate hosts must still use the pipeline's issue-level job coordination
   and must not write the same issue concurrently.
6. The attachment upload completes before the description publishes its
   attachment marker. If the upload fails, no incomplete marker is written;
   if the later description update fails, the uploaded file is an orphan and
   the description remains authoritative until a subsequent successful push.

The singular filename convention remains unchanged for this decision. A
separate decision may introduce timestamped filenames if attachment
accumulation becomes operationally significant.

## Consequences

Positive:

- A failed attachment deletion cannot make an otherwise successful push fail.
- Repeated strategy and review updates remain usable without attachment-delete
  permission.
- Description content is not replaced by a stale orphaned strategy attachment.
- Duplicate attachment selection is deterministic and based on Jira metadata.
- Concurrent local attachment writers cannot interleave an upload and marker
  update for one RHAISTRAT issue.

Negative:

- Old attachments accumulate in Jira and require a separately authorized
  cleanup process if storage or ticket usability becomes a concern.
- Humans may see several attachments with the same filename.
- Correctness depends on Jira providing reliable `created` timestamps and on
  the strategy overflow marker remaining present in the description stub.
- A successful upload followed by a failed marker update leaves an orphaned
  attachment that requires no delete permission and is safe to replace later.

## Alternatives Considered

### Continue deleting old attachments

Rejected because the CI service account lacks the required permission and the
unhandled orphan-cleanup failure is already a production problem.

### Use timestamped attachment filenames

Deferred. Timestamped names would avoid same-name ambiguity, but require
coordinated changes to all writers, readers, fixtures, and artifact staging.

### Grant attachment-delete permission to the service account

Not selected as the pipeline design decision. It would couple correctness to a
broader Jira permission and would not by itself address stale-reader behavior
or list-order ambiguity. It would also solve only the CI bot's credentials:
local SME-input flows are run by humans using their personal Jira credentials,
which can still lack attachment-delete permission and encounter the same
errors. Solving the human case would require granting every SME broad
cross-user attachment-delete permission, which is not an acceptable long-term
security or ownership model. The append-only policy therefore needs to apply
consistently across both automated and human-run flows.

### Coordinate concurrent writers with a revision marker

Deferred. A monotonic revision would require every automated and local SME
writer to produce and preserve a shared revision or source-commit ordering.
The local SME flow uses personal credentials and cannot depend on a
credential-owned counter. The per-issue writer lock gives the attachment and
marker update a clear local ordering without adding metadata to strategy
documents; distributed callers remain subject to the pipeline's issue-level
job coordination.

## Scope

The implementation applies to:

- `scripts/push_strategy.py`
- `scripts/pull_strategy.py`
- `scripts/fetch_issue.py`
- `scripts/jira_utils.py`

Validation should include unit coverage for duplicate and orphaned
attachments, a Jira-emulator overflow-then-shrink integration case, and a
manual `reprocess-strat` check against a ticket with existing orphaned
attachments.
