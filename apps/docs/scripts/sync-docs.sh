#!/bin/bash
# Sync docs/*.md → apps/docs/content/*.mdx for Nextra rendering.
# Run before build. Source of truth remains docs/*.md in repo root.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCS_DIR="$SCRIPT_DIR/../../../docs"
CONTENT_DIR="$SCRIPT_DIR/../content"

mkdir -p "$CONTENT_DIR"
echo "Syncing docs/ → content/..."

# Map: source file → target page name
declare -A DOCS_MAP=(
  ["GETTING_STARTED.md"]="getting-started.mdx"
  ["ARCHITECTURE_DIAGRAM.md"]="architecture.mdx"
  ["ARCHITECTURE_OVERVIEW.md"]="architecture-overview.mdx"
  ["ARCHITECTURE_REVIEW.md"]="architecture-review.mdx"
  ["TECHNICAL_DEEP_DIVE.md"]="technical-deep-dive.mdx"
  ["OPERATIONS.md"]="operations.mdx"
  ["WORKFLOW.md"]="workflow.mdx"
  ["LLM_PROVIDERS.md"]="llm-providers.mdx"
  ["RAG_HARNESS_SPEC.md"]="rag-harness.mdx"
  ["architecture/data-model.md"]="data-model.mdx"
  ["architecture/interfaces.md"]="interfaces.mdx"
  ["planning/MULTI_TENANT_READINESS.md"]="multi-tenant.mdx"
)

for src in "${!DOCS_MAP[@]}"; do
  target="${DOCS_MAP[$src]}"
  if [ -f "$DOCS_DIR/$src" ]; then
    cp "$DOCS_DIR/$src" "$CONTENT_DIR/$target"
    echo "  $src → $target"
  else
    echo "  SKIP: $src (not found)"
  fi
done

echo "Sync complete."
