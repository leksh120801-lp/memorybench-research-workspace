#!/usr/bin/env bash
# Builds dist/memorybench_technical_submission.zip: the docs a reviewer
# needs (README, Devpost text, architecture PNG, technical writeup) plus a
# clean source-only snapshot of backend/ and frontend/.
#
# Explicitly excluded: .env / secrets, venv/, node_modules/, FAISS index
# binaries, dist/ itself, .git/, and docs/deploy.md (account-setup specifics
# not meant for this bundle).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
ZIP_PATH="$DIST_DIR/memorybench_technical_submission.zip"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

cd "$REPO_ROOT"

echo "==> Staging docs"
mkdir -p "$STAGE_DIR/docs"
cp README.md "$STAGE_DIR/README.md"
cp docs/submission.md "$STAGE_DIR/docs/submission.md"
cp docs/architecture.png "$STAGE_DIR/docs/architecture.png"
cp docs/technical_writeup.md "$STAGE_DIR/docs/technical_writeup.md"

echo "==> Staging backend/ source"
rsync -a backend/ "$STAGE_DIR/backend/" \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache/' \
  --exclude 'data/' \
  --exclude 'bench/output/' \
  --exclude '*.faiss' \
  --exclude '*.index' \
  --exclude '.env' \
  --exclude '.DS_Store'

echo "==> Staging frontend/ source"
rsync -a frontend/ "$STAGE_DIR/frontend/" \
  --exclude 'node_modules/' \
  --exclude '.next/' \
  --exclude 'out/' \
  --exclude '.turbo/' \
  --exclude 'next-env.d.ts' \
  --exclude '.env' \
  --exclude '.env.local' \
  --exclude '.DS_Store'

echo "==> Verifying no secrets slipped in"
if find "$STAGE_DIR" -name '.env' -not -name '.env.example' | grep -q .; then
  echo "ERROR: a .env file made it into the staging dir — aborting" >&2
  find "$STAGE_DIR" -name '.env' -not -name '.env.example'
  exit 1
fi

echo "==> Building zip"
mkdir -p "$DIST_DIR"
rm -f "$ZIP_PATH"
(cd "$STAGE_DIR" && zip -rq "$ZIP_PATH" .)

echo "==> Done: $ZIP_PATH"
unzip -l "$ZIP_PATH"
