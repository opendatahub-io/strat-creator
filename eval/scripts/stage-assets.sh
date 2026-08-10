#!/usr/bin/env bash
# Stage the read-only assets the eval needs into eval/.assets/ (gitignored):
#   - assess-strat        : the scoring-rubric plugin (agent_prompt.md, skills, agents)
#   - architecture-context: the RHOAI platform docs strategy-refine/review consult
#
# The before_each hook copies these into each isolated case workspace so runs are
# hermetic (no network at eval time). Safe to run repeatedly. Run once before the
# first eval, or let the before_all hook stage on first use.
#
# Env:
#   ARCHITECTURE_CONTEXT_PATH  optional local architecture-context checkout, passed
#                              through to scripts/fetch-architecture-context.sh so
#                              overlays can be tested in the eval before pushing.
set -euo pipefail

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # -> repo/eval
REPO_ROOT="$(cd "$CONFIG_DIR/.." && pwd)"
ASSETS="$CONFIG_DIR/.assets"
mkdir -p "$ASSETS"

# 1) assess-strat (rubric + scorer agent). Strip .git so the review skill's
#    bootstrap `git pull` degrades to "use cached" instead of hitting the network.
if [ ! -f "$ASSETS/assess-strat/scripts/agent_prompt.md" ]; then
  echo "[stage] cloning assess-strat ..."
  rm -rf "$ASSETS/assess-strat"
  git clone --depth 1 https://github.com/opendatahub-io/assess-strat "$ASSETS/assess-strat"
  rm -rf "$ASSETS/assess-strat/.git"
else
  echo "[stage] assess-strat already present"
fi

# 2) architecture-context. Reuse the repo's own fetch script (sparse checkout).
if [ ! -d "$ASSETS/architecture-context/architecture" ]; then
  echo "[stage] fetching architecture-context ..."
  # Fetch into the repo's .context, then relocate into .assets (fetch script is
  # hardcoded to .context/architecture-context).
  # Honour a local checkout so overlay changes can be evaluated before they are
  # pushed upstream (same contract as the fetch script's optional path argument).
  ( cd "$REPO_ROOT" && bash scripts/fetch-architecture-context.sh ${ARCHITECTURE_CONTEXT_PATH:+"$ARCHITECTURE_CONTEXT_PATH"} )
  rm -rf "$ASSETS/architecture-context"
  cp -R "$REPO_ROOT/.context/architecture-context" "$ASSETS/architecture-context"
  rm -rf "$ASSETS/architecture-context/.git"
else
  echo "[stage] architecture-context already present"
fi

echo "[stage] assets ready under $ASSETS"
ls -1 "$ASSETS"
