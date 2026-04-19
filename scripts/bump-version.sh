#!/usr/bin/env bash
# scripts/bump-version.sh
# Bump the version in pyproject.toml.
#
# Usage:
#   scripts/bump-version.sh patch   # 0.1.0 → 0.1.1
#   scripts/bump-version.sh minor   # 0.1.0 → 0.2.0
#   scripts/bump-version.sh major   # 0.1.0 → 1.0.0
#
# Outputs the new version string to stdout.
set -euo pipefail

PYPROJECT="$(cd "$(dirname "$0")/.." && pwd)/pyproject.toml"

if [[ ! -f "$PYPROJECT" ]]; then
  echo "error: pyproject.toml not found at $PYPROJECT" >&2
  exit 1
fi

BUMP="${1:-}"
if [[ "$BUMP" != "patch" && "$BUMP" != "minor" && "$BUMP" != "major" ]]; then
  echo "Usage: $0 [patch|minor|major]" >&2
  exit 1
fi

# Extract current version.
CURRENT=$(grep -E '^version = "' "$PYPROJECT" | head -1 | sed 's/version = "//;s/"//')
if [[ -z "$CURRENT" ]]; then
  echo "error: could not parse version from $PYPROJECT" >&2
  exit 1
fi

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

# Update pyproject.toml in-place (first occurrence of version = "...").
sed -i "0,/^version = \"${CURRENT}\"/s//version = \"${NEW_VERSION}\"/" "$PYPROJECT"

echo "$NEW_VERSION"
