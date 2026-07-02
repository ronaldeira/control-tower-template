#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Clean tree passes.
echo "hello world" > "$tmp/ok.txt"
bash "$here/scripts/check_secrets.sh" "$tmp" || { echo "FAIL: clean tree flagged"; exit 1; }

# Planted fake AWS key is caught.
echo "AKIAIOSFODNN7EXAMPLE" > "$tmp/leak.txt"
if bash "$here/scripts/check_secrets.sh" "$tmp"; then
  echo "FAIL: secret not caught"; exit 1
fi
echo "PASS"
