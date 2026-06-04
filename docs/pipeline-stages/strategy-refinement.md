# Strategy Refinement

> **Owner:** strat-creator CI pipeline
> **Last verified:** 2026-05-21

## What Happens

The `strategy-refine` skill transforms the strategy stub into a full implementation plan. It fetches architecture context from [opendatahub-io/architecture-context](https://github.com/opendatahub-io/architecture-context) and uses it to ground the strategy in real platform architecture.

!!! info "This skill runs twice in the lifecycle"
    **First pass (CI):** The pipeline runs `strategy-refine` automatically after strategy creation. This produces the initial technical approach with no human input.

    **Second pass (human review):** After CI scoring, a staff engineer may run `strategy-refine` again locally via `/strategy-refine RHAISTRAT-NNNN`. This time, the skill incorporates any corrections added to the "Staff Engineer / SME Input" section, producing an improved strategy.

    The same skill is used both times. The difference is whether human input exists in the strategy file.

```mermaid
flowchart TD
    A["Strategy stub"] --> B["Fetch architecture\ncontext"]
    B --> C["Apply size-scaled\ntemplate"]
    C --> D["Add technical\napproach"]
    D --> E["Add dependencies\n& NFRs"]
    E --> F["Incorporate Staff\nEngineer Input"]
    F --> G["Refined strategy"]
```

### What Gets Added

- **Technical approach**: How to implement the feature, grounded in actual component architecture
- **Dependencies**: Which components, teams, and APIs are involved
- **Impacted teams/components**: Who needs to coordinate
- **Non-functional requirements**: Performance, security, observability, testing requirements
- **Effort estimate**: Size-appropriate level of detail (S/M/L/XL templates)

### Architecture Context

The refinement stage uses architecture context (component docs, dependency maps) fetched from [opendatahub-io/architecture-context](https://github.com/opendatahub-io/architecture-context). This includes any [overlays](../reference/architecture-context.md) that patch the base context.

### Large Strategy Handling

When a refined strategy exceeds Jira's description size limit (~32K characters), the full strategy is stored as a Jira attachment (`RHAISTRAT-NNNN-strategy.md`) and the Jira description shows a TL;DR stub with a note pointing to the attachment. This is handled transparently by the pipeline.

### Staff Engineer / SME Input

If a `## Staff Engineer / SME Input` section exists in the strategy file, refine incorporates it into the regenerated strategy. This is how human corrections flow into the automated output.

!!! note
    This section is empty on the first CI pass. It only gets populated during [human review](human-review-signoff.md) when a staff engineer or SME adds corrections after reviewing the CI-generated strategy.

### Labels Applied

- `strat-creator-auto-refined` on the RHAISTRAT ticket

## What Triggers This Stage

- A strategy stub exists from [Strategy Creation](strategy-creation.md)

## What It Produces

- Updated `artifacts/strat-tasks/RHAISTRAT-NNNN.md` with full strategy content
- Architecture context fetched to `.context/architecture-context/`

## Next Stage

[Strategy Review](strategy-review.md): The refined strategy is scored and reviewed.
