#!/usr/bin/env bash
# Run the eval only when something that affects answers changed since the last recorded run.
# Wire this as a post-merge hook on the host (or call it from the deploy step).
set -euo pipefail
cd "$(dirname "$0")/.."
last=$(ls evals/history/*.json 2>/dev/null | grep -v -- '-dry' | tail -1 || true)
last_sha=$( [ -n "$last" ] && basename "$last" .json | sed -E 's/^[0-9-]{11}//' || echo "" )
if [ -n "$last_sha" ] && git cat-file -e "$last_sha" 2>/dev/null; then
  if git diff --quiet "$last_sha" HEAD -- corpus askben/llm.py askben/policy.yaml askben/pipeline.py askben/config.py evals/golden.yaml; then
    echo "eval: nothing relevant changed since $last_sha"; exit 0
  fi
fi
python -m askben.ingest
python -m evals.run_eval
