#!/usr/bin/env bash
# Generic host + running-service snapshot for local-mode adopters.
# Prints Markdown to stdout. Contains no hardcoded hosts/paths.
set -uo pipefail
echo "# Environment snapshot"
echo
echo "_Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) — do not edit by hand._"
echo
echo "## Host"
echo '```'
uname -a 2>/dev/null || true
echo '```'
echo
echo "## Disk (root)"
echo '```'
df -h / 2>/dev/null | tail -n +1 || true
echo '```'
echo
if command -v pm2 >/dev/null 2>&1; then
  echo "## pm2"
  echo '```'
  pm2 ls 2>/dev/null || true
  echo '```'
fi
if command -v docker >/dev/null 2>&1; then
  echo "## docker"
  echo '```'
  docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null || true
  echo '```'
fi
