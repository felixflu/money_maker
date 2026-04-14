#!/usr/bin/env bash
# Setup local test environment for backend (Python) and frontend (Node.js).
# Designed for use by polecats and the refinery — avoids Docker to prevent
# container-name conflicts across worktrees.
#
# Usage: ./scripts/setup-test-env.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- Backend: Python venv + dependencies ---

VENV_DIR="$REPO_ROOT/backend/.venv"

# Prefer python3.11 (matches Dockerfile), fall back to python3.12, then python3
PYTHON=""
for candidate in python3.11 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: No python3 found."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python venv at $VENV_DIR (using $PYTHON)..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

echo "Installing backend dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_ROOT/backend/requirements.txt"

# --- Frontend: Node.js dependencies ---

# Use nvm to ensure a compatible Node version (>=18 for Next.js 14)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck source=/dev/null
    . "$NVM_DIR/nvm.sh"
    # Use Node 20 if available, otherwise install it
    if nvm ls 20 >/dev/null 2>&1; then
        nvm use 20 --silent
    else
        echo "Installing Node 20 via nvm..."
        nvm install 20
    fi
else
    # No nvm — check if system node is new enough
    NODE_MAJOR="$(node --version 2>/dev/null | sed 's/v\([0-9]*\).*/\1/' || echo 0)"
    if [ "$NODE_MAJOR" -lt 18 ]; then
        echo "ERROR: Node >= 18 required (found $(node --version 2>/dev/null || echo 'none'))."
        echo "Install nvm or a newer Node version."
        exit 1
    fi
fi

echo "Installing frontend dependencies..."
# Use a project-local npm cache to avoid EACCES on shared caches
export npm_config_cache="$REPO_ROOT/frontend/.npm-cache"
cd "$REPO_ROOT/frontend"
npm ci --ignore-scripts 2>/dev/null || npm install
cd "$REPO_ROOT"

echo "Test environment ready."
echo "  Backend venv: $VENV_DIR"
echo "  Frontend node_modules: $REPO_ROOT/frontend/node_modules"
