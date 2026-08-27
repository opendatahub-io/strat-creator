# ADR-0005: Move Assess-Strat into Strat-Creator

## Status

Accepted

## Context

`strat-creator` uses `assess-strat` to score strategies during
`strategy-review`. The current integration treats `assess-strat` as a separate
Claude Code plugin: a bootstrap script clones it at runtime, copies its skills
and agent definitions into the working tree, and leaves the scoring scripts
under `.context/assess-strat/`.

This arrangement has produced recurring failures in agent registration and
path resolution. In particular, the scorer can be unavailable as a runtime
agent even after its definition has been copied, and `strategy-review` has
hardcoded paths that do not work when the plugin is loaded through a different
mechanism. The runtime clone also makes the version of the scorer and rubric
depend on external repository state.

`assess-strat` has no consumers outside `strat-creator`, so the repository
boundary does not provide a required ownership or reuse boundary.

## Decision

Move the complete functional assess-strat implementation into
`strat-creator` and make this repository its source of truth. The migration
will preserve the functionality that can be used by this project:

1. Add the scorer agent as `.claude/agents/strat-scorer.md`.
2. Preserve the `/assess-strat` and `/export-rubric` skills under
   `.claude/skills/`, adapting their plugin-root and script-path resolution to
   the in-repository layout.
3. Move the rubric and scoring/run-management scripts into an in-repository
   `scripts/assess-strat/` directory, including the single-strategy and batch
   workflows, result parsing, summaries, and rubric export.
4. Migrate the assess-strat test suite and rewrite its path, packaging, and
   environment assumptions as needed. Update existing `strat-creator` tests
   that assert the bootstrap-based workflow.
5. Update `strategy-review`, project permissions, evaluation staging, and
   documentation to use the in-repository files directly.
6. Delete `scripts/bootstrap-assess-strat.sh` and remove the associated
   runtime clone, `CLAUDE_PLUGINS` guard, generated-file exceptions, and
   `.context/assess-strat` path contract once migration is complete.

The standalone plugin's repository-hosting and packaging infrastructure—its
plugin manifests, standalone CI workflow, and package-level build metadata—is
not copied into `strat-creator` because it does not provide runtime
functionality after the move. The standalone repository will be archived or
redirected after all references and consumers have been checked.

This decision does not adopt or depend on the proposed plugin taxonomy;
assess-strat remains an ordinary in-repository skill and agent for now.

## Consequences

Positive:

- The scorer, rubric, scripts, skills, and tests are versioned with the
  pipeline that consumes them.
- `strategy-review` has stable paths regardless of how Claude Code starts the
  project.
- Runtime cloning and mid-session agent installation are eliminated.
- The standalone scoring skill remains available instead of being reduced to
  an internal reviewer implementation.

Negative:

- `strat-creator` owns and maintains the assess-strat implementation and its
  tests.
- The repository gains the assess-strat scripts and test surface.
- Any future external consumer would need a new extraction or shared-package
  decision.
- The standalone repository must be retired carefully so stale references do
  not recreate the bootstrap dependency.

## Alternatives Considered

### Keep the repositories separate and repair bootstrap

Rejected. Agent registration and path resolution are independent failure
surfaces created by the same runtime bootstrap boundary. Repairing one does not
remove the other, and no external consumer requires the separation.

### Move only `strat-scorer.md`

Rejected. The agent depends on the shared rubric, and the review pipeline also
depends on result parsing, summaries, and rubric export. Moving only the agent
would preserve the path and versioning problems.

### Keep the full plugin as a vendored runtime directory

Rejected. Vendoring the entire plugin would retain unnecessary plugin metadata
and obscure which files are part of `strat-creator`'s supported interface.
The functional files and tests will be integrated explicitly instead.

## Related

- RHAIFIRST-406: scorer agent registration failure
- RHAIFIRST-438: recurring scorer agent registration failure
- RHAIFIRST-532: hardcoded assess-strat path failure
- RHAIFIRST-109: repository transfer and retirement checklist
