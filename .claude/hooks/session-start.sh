#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

HUGO_VERSION="0.139.0"

# ── Install Hugo extended if not present or version mismatch ──────────────────
if ! hugo version 2>/dev/null | grep -q "$HUGO_VERSION"; then
  echo "Installing Hugo extended v${HUGO_VERSION}..."
  curl -fsSL \
    "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.tar.gz" \
    | tar -xz -C /usr/local/bin hugo
  echo "Hugo installed: $(hugo version)"
fi

# ── Validate the site builds cleanly ─────────────────────────────────────────
cd "$CLAUDE_PROJECT_DIR"
echo ""
echo "Building site..."
if hugo --minify --quiet 2>&1; then
  echo "✔ Hugo build OK"
else
  echo "✖ Hugo build FAILED — check templates before editing"
fi

# ── Session orientation ───────────────────────────────────────────────────────
echo ""
echo "━━ Almond Farm ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Branch : $(git branch --show-current)"
CHANGED=$(git status --short | wc -l | tr -d ' ')
if [ "$CHANGED" -gt 0 ]; then
  echo "Status : $CHANGED uncommitted change(s)"
  git status --short
else
  echo "Status : clean"
fi
echo ""
echo "Recent commits:"
git log --oneline -3
echo ""

# ── Remind about empty sections ───────────────────────────────────────────────
EMPTY_SECTIONS=""
for section in gaming art movies drinks body gadgets; do
  count=$(find "$CLAUDE_PROJECT_DIR/content/$section" -name "*.md" ! -name "_index.md" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -eq 0 ]; then
    EMPTY_SECTIONS="$EMPTY_SECTIONS $section"
  fi
done
if [ -n "$EMPTY_SECTIONS" ]; then
  echo "Empty sections:$EMPTY_SECTIONS"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
