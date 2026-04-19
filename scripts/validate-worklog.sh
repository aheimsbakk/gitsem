#!/usr/bin/env bash
# scripts/validate-worklog.sh
# Validate that all worklogs in docs/worklogs/ conform to the required front-matter schema.
#
# Usage:
#   scripts/validate-worklog.sh
#
# Exits 0 if all worklogs are valid, >0 otherwise.
set -euo pipefail

WORKLOGS_DIR="$(cd "$(dirname "$0")/.." && pwd)/docs/worklogs"
REQUIRED_KEYS=("when" "why" "what" "model" "tags")

if [[ ! -d "$WORKLOGS_DIR" ]]; then
  echo "error: worklogs directory not found: $WORKLOGS_DIR" >&2
  exit 1
fi

FILES=("$WORKLOGS_DIR"/*.md)
if [[ ${#FILES[@]} -eq 0 ]] || [[ ! -f "${FILES[0]}" ]]; then
  echo "No worklogs found in $WORKLOGS_DIR — nothing to validate."
  exit 0
fi

ERRORS=0

for FILE in "${FILES[@]}"; do
  [[ -f "$FILE" ]] || continue
  BASENAME=$(basename "$FILE")

  # Check front-matter delimiters exist.
  if ! grep -q "^---$" "$FILE"; then
    echo "FAIL [$BASENAME]: missing YAML front-matter delimiters (---)" >&2
    ERRORS=$((ERRORS + 1))
    continue
  fi

  for KEY in "${REQUIRED_KEYS[@]}"; do
    if ! grep -qE "^${KEY}:" "$FILE"; then
      echo "FAIL [$BASENAME]: missing required front-matter key '${KEY}'" >&2
      ERRORS=$((ERRORS + 1))
    fi
  done

  # Check filename format: YYYY-MM-DD-HH-mm-{desc}.md
  if ! [[ "$BASENAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}-.+\.md$ ]]; then
    echo "FAIL [$BASENAME]: filename does not match YYYY-MM-DD-HH-mm-{desc}.md" >&2
    ERRORS=$((ERRORS + 1))
  fi
done

if [[ $ERRORS -gt 0 ]]; then
  echo "$ERRORS worklog validation error(s) found." >&2
  exit 1
fi

echo "All worklogs valid (${#FILES[@]} checked)."
exit 0
