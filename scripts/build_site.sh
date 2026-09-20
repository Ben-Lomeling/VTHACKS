#!/usr/bin/env bash
# Rebuild the site that the API serves (frontend/dist is committed, so Render never builds anything).
# Run after any frontend change, then commit frontend/dist.
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm ci
npm run build
echo "Built frontend/dist — commit it so the deploy picks it up."
