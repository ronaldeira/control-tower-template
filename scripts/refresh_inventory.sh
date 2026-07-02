#!/usr/bin/env bash
# Regenerate the gitignored environment snapshot.
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$here/inventory"
bash "$here/scripts/snapshot_env.sh" > "$here/inventory/environments.generated.md"
echo "wrote inventory/environments.generated.md"
