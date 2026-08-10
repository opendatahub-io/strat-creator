# Coverage: `/strategy-refine` argument-parsing refusal (RHAIFIRST-399)

Status: **proposed** — judges below are not yet in `eval.yaml`. Verify the
`steps/refine/stdout.log` path with a throwaway single-case run before relying on
the refusal-diagnosis branch (see [Verify first](#verify-first)).

## The bug

`/strategy-refine RHAISTRAT-2353` **intermittently** refuses its argument —
returning "No strategy key provided / this appears to be a placeholder / a
reference to the instructions" instead of processing the strategy. Reported as a
"bad dice roll": same command, different outcome across runs.

- **Model-sensitive**: fails often on haiku/sonnet; opus tends to recover (reads
  the whole payload). The reporting user's `settings.json` had `"model": "haiku"`.
- **Root cause**: the skill uses `context: fork` frontmatter; the
  argument reaches the model as an XML blob
  (`<command-name>/<command-args>RHAISTRAT-2353</command-args>`). Deleting
  `context: fork` makes it work consistently. `/strategy-pull` (no fork) is fine.
- **Side effect**: no refined strategy is produced (and, in prod,
  `local/strat-history/RHAISTRAT-NNNN/` is never created — RHAIFIRST-400).

## Can this eval catch it? Yes

The harness invokes the skill as a **real slash command**: `ClaudeCodeRunner`
builds the literal `/strategy-refine <args>` and pipes it to `claude --print`
(agent-eval-harness `agent_eval/agent/claude_code.py:143-149`), with skills
symlinked frontmatter-intact. So the real command-args pipeline, the
`<command-args>` XML, and `context: fork` are all exercised — an eval run
reproduces the trigger, it doesn't simulate it. (Reproduction fidelity was
independently verified against the harness code.)

**Caveat:** the harness always pins `--model`, so it can *deliberately* test
haiku but cannot reproduce the *accidental* `settings.json` model default. That
one belongs in a frontmatter lint / `eval-check`, not a run.

**The outcome is already caught.** A refusal writes no `strat-tasks/*.md`, so the
existing `files_exist` / `strategy_nonempty` gates (both `min_pass_rate: 1.0`)
already go red. The judges below add **diagnosis** (attribute the red to this bug,
not a generic missing file) and, via the matrix, a **per-model flake rate**.

## Gotcha: which step a judge can see

This eval has two `execution.steps` (refine, review). **A judge's
`outputs["conversation"]` / `outputs["events"]` contain only the FINAL step
(review) + its subagents — not refine's top-level refusal.**

- `execute.py:1148-1153` writes the case-level `stdout.log` = the last step.
- `collect.py._generate_events_json` builds `events.json` from that single
  `stdout.log` + `subagents/` only — it does **not** concatenate `steps/*/stdout.log`.
- `extract_conversation_text` emits root-level assistant text and filters
  subagents by `parent_tool_use_id`.

Note also that `strategy-refine` is itself a `context: fork` skill, so its **tool
calls are not in `steps/refine/stdout.log`** — that file holds only `init` /
`task_started` / the final assistant turn / `result`. The refusal text IS in that
final turn, so the judges below work as written. Refine's tool calls go to a subagent
transcript (`cases/<case>/subagents/*.jsonl`, captured by the harness SubagentStop
hook). That directory is per-case rather than per-step, but each transcript records
the `sessionId` of the session that spawned it, and each step has its own session —
which is how `architecture_context_used` attributes grounding to the refine step.

The refine refusal is a top-level assistant turn in the **refine** step, saved at
`<case_dir>/steps/refine/stdout.log` (`execute.py:1096-1099`), reachable via
`outputs["case_dir"]`. **So do not scan `conversation` for the refusal.**

## Proposed judges

Add to the `judges:` list in `eval.yaml`:

```yaml
  # --- Argument recognition (RHAIFIRST-399). strategy-refine must ACT on its
  #     {strat_id} arg, not misread it as a placeholder and refuse. The refusal
  #     is a top-level turn in the REFINE step, which is NOT in {{ conversation }}
  #     /events (those hold the final step = review + subagents; execute.py:1148-1153,
  #     collect.py _generate_events_json). So read refine's own stdout. Primary
  #     signal stays the produced artifact, so this is correct even if the per-step
  #     log is absent; the refusal scan only names the failure.
  - name: refine_recognized_arg
    description: strategy-refine acted on its strat_id argument (did not refuse it as a placeholder — RHAIFIRST-399).
    check: |
      import os, glob
      files = outputs.get("files", {})
      produced = any("strat-tasks" in p and p.endswith(".md") for p in files)
      markers = (
          "No strategy key provided",
          "appears to be a placeholder",
          "reference to the instructions",
          "which strategy you'd like me to refine",
          "provide the strategy key",
      )
      # ONLY the refine step. A steps/*/stdout.log fallback would also read the
      # review step, where a reviewer quoting a refusal phrase would be misread as
      # refine refusing its own argument.
      refine_out = ""
      base = outputs.get("case_dir", "")
      for fp in glob.glob(os.path.join(base, "steps", "refine", "stdout.log")):
          try:
              refine_out += open(fp, encoding="utf-8", errors="replace").read()
          except OSError:
              pass
      hit = next((m for m in markers if m in refine_out), None)
      if not produced:
          why = (f"refused its argument (matched {hit!r})" if hit
                 else "produced no strat-tasks/*.md (arg not recognized or step failed)")
          return False, f"strategy-refine {why}"
      if hit:
          return True, f"recovered — voiced placeholder-doubt ({hit!r}) but still produced a strategy"
      return True, "acted on its strat_id argument"

  # --- Correct-id recognition. Confirms the pipeline acted on THIS case's
  #     strat_id (catches misread-to-placeholder / wrong-id). Path-independent.
  - name: strat_id_honored
    description: The produced review corresponds to the case's own strat_id (not a placeholder or wrong id).
    check: |
      import re
      # Fail closed: a malformed strat_id (e.g. "RHAIRFE-ABC") must not silently
      # skip the identity check, or a wrong-id run scores as a pass.
      raw = outputs.get("inputs", "") or ""
      m = re.search(r"strat_id\W+(\S+)", raw)
      if not m:
          return False, "no strat_id in inputs; cannot verify identity"
      strat_id = m.group(1).strip("\"'")
      if not re.fullmatch(r"STRAT-\d+", strat_id):
          return False, f"strat_id {strat_id!r} is not the canonical STRAT-<n> form"
      review = next((p for p in outputs.get("files", {})
                     if p.endswith("-review.md") and not p.endswith("-review-comment.md")), None)
      if review is None:
          return False, f"no review file for {strat_id}"
      # Check the document, not just the path: a wrong review saved under a matching
      # filename would otherwise pass.
      body = outputs.get("files", {}).get(review) or ""
      if not isinstance(body, str):
          return False, f"review {review!r} is not readable text"
      ok = strat_id in body
      return ok, (f"review body honors {strat_id}" if ok
                  else f"review {review!r} body does not mention {strat_id}")
```

Add to `thresholds:`:

```yaml
  refine_recognized_arg: {min_pass_rate: 1.0}
  strat_id_honored:       {min_pass_rate: 1.0}
```

Design notes:
- `refine_recognized_arg` FAILs only when `refused AND not produced`. A run that
  voiced doubt but still produced a strategy **passes** (opus recovers this way) —
  we gate on real failures, and the matrix surfaces the flake rate.
- Both use only `outputs` keys the harness guarantees (`files`, `inputs`,
  `case_dir`), so they degrade gracefully if `steps/refine/stdout.log` is missing.

## The part that actually addresses "bad dice roll" — the matrix

A single run per model can pass by luck. Extend the (commented) `matrix:` block to
include the failing model class and enough replications, then run `/eval-anova`:

```yaml
matrix:
  factors:
    model:
      - claude-opus-4-6
      - claude-sonnet-4-6
      - claude-haiku-4-5     # the model class that refused in the thread
  replications: 8            # dice-roll bug: one run per model isn't enough
```

`/eval-anova` then reports `refine_recognized_arg` as a **pass rate per model**
with a cost/quality Pareto — answering both thread asks: "real bug or luck?"
(haiku pass rate ≪ 1.0 = real) and "cheapest model that works?" (the Pareto
frontier).

## Verify first

Before trusting the refusal-diagnosis branch, confirm the per-step log lands where
the judge expects:

```bash
/eval-run --config eval/eval.yaml --model claude-opus-4-6 \
  --cases <one-small-case-id>
ls eval/runs/*/cases/*/steps/refine/stdout.log   # should exist
```

If it does, the `refine_recognized_arg` diagnosis branch is live. If not, the
judge still works off the artifact signal (`produced`), just without the
refusal-string attribution.
