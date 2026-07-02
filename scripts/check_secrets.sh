#!/usr/bin/env bash
# Generic, provider-agnostic secret scanner. No project-specific terms.
set -uo pipefail
DIR="${1:-.}"

PATTERN='ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|://[^/@[:space:]]+:[^/@[:space:]]+@'

if grep -rEIn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.superpowers --exclude-dir=__pycache__ --exclude=check_secrets.sh --exclude=test_check_secrets.sh "$PATTERN" "$DIR"; then
  echo "❌ FAIL: a generic secret pattern was found (see matches above)." >&2
  exit 1
fi
echo "✅ PASS: no generic secret patterns found."
exit 0
