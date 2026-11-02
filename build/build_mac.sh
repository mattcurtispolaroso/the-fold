#!/usr/bin/env bash
# Build The Fold for macOS — produces dist/The Fold.app
# Run from the project root: ./build/build_mac.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Building The Fold (macOS)"
echo "    Root: $ROOT"

cd "$ROOT"

# Clean previous build artefacts
rm -rf dist/The\ Fold.app build/__pycache__

# Run PyInstaller with the shared spec
pyinstaller build/the_fold.spec \
    --distpath dist \
    --workpath build/_pyinstaller_work \
    --noconfirm \
    --clean

echo ""
echo "==> Done. App bundle at: dist/The Fold.app"
echo "    Launch with: open 'dist/The Fold.app'"
