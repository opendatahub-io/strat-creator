# strat-creator eval

An [agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness) eval
that covers the **end-to-end strat-creator pipeline** and **differentiates strategy
quality across models**.

For each approved RFE, it reproduces the production `strat-pipeline` flow —
`strategy-create` → `strategy-refine` → `strategy-review` — then scores the refined
strategy with an independent, held-constant judge using the same **assess-strat**
rubric the pipeline itself uses (Feasibility / Testability / Scope / Architecture,
0–2 each = **/8**).

## How it works

- **Runner + steps:** the native `claude-code` runner with a two-step
  `execution.steps` pipeline. `strategy-create` is mechanical (a verbatim RFE copy),
  so its output stub is staged by a `before_each` hook; the two LLM-driven,
  quality-determining stages run as **native steps** — `refine` then `review` —
  sharing one per-case workspace and handing off through `artifacts/` on disk,
  exactly like prod. Each step is a fresh Claude session (real topology), so
  cross-session handoff behaviour is preserved.
- **Instrumentation:** the harness captures each step's stream-json → `events.json`
  (`traces.events: true`) — giving judges the reasoning/tool trace (used by
  `architecture_context_used`) — plus subagent transcripts and **per-step cost/tokens
  in `run_result.json`** (summed per case, including the scorer + all 4 forked
  reviewers). No hand-rolled `metrics.json` and no cli driver: the harness owns
  staging, execution, collection, and metrics natively.
- **Hermetic:** every step runs `--dry-run` (no Jira writes) and the stub has
  `jira_key=null` (Jira label gates are bypassed), so no live Jira. `assess-strat`
  and `architecture-context` are staged from `eval/.assets/` (by the `before_all`
  hook) into each case workspace by the `before_each` hook — which rebuilds a real
  (not symlinked) `.claude/skills` + `.context` so the strat skills' bootstrap writes
  stay inside the throwaway workspace, never back into the repo.
- **Environment parity:** the case workspace is made to look like prod CI, not like a
  developer laptop. The `before_each` hook writes `.claude/settings.local.json` with
  `disableAllHooks: true` so personally-installed plugins can't fire (memsearch, for
  one, writes `.memsearch/` into the workspace, injects "Recent Memory" context, and
  spawns a per-turn summarizer — none of which prod has), and it pre-stages the
  `strat-scorer` agent into `.claude/agents/` because Claude Code registers agent
  types at *startup*, so the review skill's mid-session bootstrap is too late and the
  scorer would silently fall back to a generic agent.
- **Permissions:** isolated workspaces are untrusted, so recent Claude Code drops the
  workspace `settings.json` allow-list. The runner uses `permission_mode: dontAsk`
  with a trust-independent allow-list (`permissions.allow` → `--allowed-tools`). Keep
  that list COMPLETE — in `dontAsk` mode every sub-command of a compound Bash call
  must prefix-match a rule, or the call is silently denied.
- **One case = one RFE** (`execution.mode: case`) — the natural repeated-measures
  unit for `/eval-anova`.
- **Model under test** is `models.skill` (default `claude-opus-4-6`, the prod model;
  override with `--model`). The **judge** (`models.judge`, default `claude-opus-4-8`)
  is held constant across candidates to avoid self-preference bias.

## Judges

| Judge | Type | What it measures |
|---|---|---|
| `feasibility_score` / `testability_score` / `scope_score` | LLM (0–2, `samples: 3`) | Independent per-dimension rubric score of the refined strategy — **the model-differentiation signal**. Feasibility carries most of it (real strategies cluster at 1 there). |
| `architecture_score` | **agent** (0–2, `samples: 3`) | Grounded Architecture score — a native `agent:` judge (held-constant judge model run as a *tool-using agent* with `[Read, Grep, Glob]`) that Greps/Reads `.context/architecture-context` to validate the strategy's components/CRDs/APIs. A plain LLM judge can't open the docs and inflates this to ~2.0; the agent grounds it. The harness stages an isolated workspace (strategy under `./strat-tasks/`, docs read-only under `./.context/architecture-context`) and reads `output/score.json`. |
| `pipeline_total` | check (0–8) | The pipeline's **own** assess-strat total (from the review frontmatter) — reported for pipeline-vs-independent-judge agreement. |
| `files_exist`, `strategy_nonempty` | check (gate) | The pipeline produced a filled strategy + a scored review. |
| `frontmatter_valid` | check (gate) | Review frontmatter matches the `strat-review` schema (4 int scores, total = sum, valid enums). |
| `recommendation_consistency` | check (gate) | The pipeline's recommendation matches the deterministic assess-strat verdict of its own scores. |
| `architecture_context_used` | check (event trace) | The pipeline consulted the architecture-context docs (Read/Grep/Glob/Bash, incl. subagents). |
| `cost_budget` | builtin | Per-case pipeline cost (refine + review, summed across steps in `run_result.json`); Pareto input. |

The independent per-dimension total = sum of the four judge means. The four judge
prompts (`prompts/*-judge.md`) are the verbatim assess-strat rubric with its
calibration anchors, so the eval scores on the same axis production CI uses.

## Prerequisites

- The `claude` CLI on `PATH`, authenticated the same way prod runs it (Vertex:
  `CLAUDE_CODE_USE_VERTEX=1` + `ANTHROPIC_VERTEX_PROJECT_ID`; or an Anthropic API key).
- Read access to the internal prod data repo **`strat-pipeline-data`** (for building
  the dataset) and to **`assess-strat`** + **`architecture-context`** (staged assets).
- The **agent-eval-harness plugin** providing `/eval-run`, `/eval-anova`,
  `/eval-compare` — recent enough to include the native **`agent:` judge** type
  (PR #170) and **`execution.steps`** multi-step support (PR #172). Both are merged
  to `main`, so a current plugin has them; update an older install.

## Setup (one-time)

The dataset and staged assets are **git-ignored** — they contain internal RFE and
strategy content and are rebuilt locally.

```bash
# 1) Clone the internal prod data repo (source of real RFE snapshots + reference
#    scores). Ask the strat-pipeline maintainers for its location; the build script
#    takes any checkout via --data-repo.
git clone --depth 1 <strat-pipeline-data repo> /tmp/strat-pipeline-data

# 2) Build the ~24-case stratified dataset from real prod triples
python3 eval/scripts/build_dataset.py            # --data-repo <path> --force to override

# 3) Stage read-only assets (assess-strat rubric + architecture-context)
bash eval/scripts/stage-assets.sh                # also runs from the before_all hook if missing
```

The dataset spans the full quality range (rubric totals 1–8, all sizes S–XL,
including the scarce reject / zero-dimension cases) so models actually separate. The
curated RFE key list lives in `eval/scripts/build_dataset.py` (`CURATED`).

## Run

```bash
# Cheap smoke test first — one small (S) case; --cases takes EXACT case IDs (space-separated)
/eval-run --config eval/eval.yaml --model claude-opus-4-6 \
  --cases RHAIRFE-912-configuration-persistence-for-gen-ai-studio

# Full run against the prod model (all 24 cases)
/eval-run --config eval/eval.yaml --model claude-opus-4-6
```

Each run writes `eval/runs/<run-id>/` with `summary.yaml`, `report.html`,
`run_result.json`, and per-case artifacts (incl. per-step `steps/<id>/` traces).
Reports show per-dimension judge means, the pipeline's own totals, the deterministic
gates, and cost.

### Cost controls (two layers)

1. **Per-step hard cap** — `execution.max_budget_usd` (default 8.0) is passed to each
   step's `claude --max-budget-usd`, which **aborts a step** that exceeds it. It's
   per-step, and a case runs two steps (refine + review), so worst case is ~2×. Set
   it as a **runaway guard**, not a tight budget (a review that hits the cap
   mid-scoring truncates and fails that step). Per-step budget/timeout are enforced
   natively by the harness.
2. **Per-case total gate** — the `cost_budget` judge reads the summed per-case cost
   (refine + review, including subagents) from `run_result.json` and flags cases over
   `max_cost_usd` (default 12.0). Post-hoc detection + a Pareto input. The
   `architecture_score` agent judge's cost is attributed to that judge, not the case.

Calibrate both after the smoke test reveals real per-case cost. Ballpark: each case
is two opus steps (review forks a scorer + 4 prose reviewers) **plus** the grounded
architecture agent judge (`samples: 3`), so the full 24-case run is substantial
(order of an hour, tens of dollars). **Start small.**

## Model comparison (Phase 2)

Uncomment the `matrix:` block in `eval.yaml` and run:

```bash
/eval-anova --config eval/eval.yaml       # sweeps the model factor with replications
/eval-compare eval/runs                   # side-by-side model comparison report
```

`/eval-anova` reports per-judge **F / p / effect-size** (accounting for case
difficulty) and a cost/quality **Pareto** view — i.e. *which model produces better
strategies, and is the difference significant.* The judge model stays fixed across
all cells. Add `--baseline <run-id>` to activate the blind `pairwise` judge
(`prompts/pairwise-judge.md`).

## Files

```
eval/
  eval.yaml                 # harness config (claude-code runner, execution.steps, hooks, judges, matrix[commented])
  prompts/*.md              # 4 per-dimension rubric judges (architecture-agent-judge.md is the agent judge) + pairwise
  scripts/build_dataset.py  # materializes dataset/cases from strat-pipeline-data
  scripts/stage-assets.sh   # before_all hook: stages assess-strat + architecture-context into .assets/
  scripts/stage-case.sh     # before_each hook: rebuilds the per-case project tree + stages the create stub
  dataset/cases/<id>/       # (git-ignored) input.yaml, stub.md, rfe-original.md, reference/, annotations.yaml
  .assets/                  # (git-ignored) assess-strat + architecture-context
  runs/                     # (git-ignored) eval run outputs
```

## Fidelity notes & limitations

- **Create is staged, not LLM-run.** `strategy-create` copies the RFE verbatim into a
  stub and sets frontmatter — mechanical work that doesn't generate strategy content,
  so a `before_each` hook stages its output deterministically, preserving the real
  create→refine handoff while focusing the eval on the stages that determine quality.
  A full create-via-emulator mode (seeding the repo's jira-emulator) is a possible
  follow-up for end-to-end-including-create fidelity.
- **The Architecture judge is a native agent judge.** It Greps/Reads the real arch
  docs to validate claims, so it doesn't inflate to 2.0 like a plain LLM judge would.
  The old text-only prompt is kept at `prompts/architecture-judge.md` if you want the
  cheap variant. The first full run (2026-07-31) used the text-only judge — its
  A-scores (mean 2.0) are inflated; re-score with the agent judge for a trustworthy
  Architecture number.
- **`expected_*` in `annotations.yaml` are single-sample prod references** — use them
  as calibration anchors (with `score_tolerance`), not hard gates.
- Pin the `claude` CLI version if you need run-to-run reproducibility (prod doesn't).

## Robustness coverage

- **[argument-parsing-coverage.md](argument-parsing-coverage.md)** — proposed judges
  (`refine_recognized_arg`, `strat_id_honored`) + matrix wiring to cover the flaky
  `/strategy-refine` argument-parsing refusal (RHAIFIRST-399), and the multi-step
  gotcha (a judge sees the *review* step, not refine's refusal — read
  `steps/refine/stdout.log`).
