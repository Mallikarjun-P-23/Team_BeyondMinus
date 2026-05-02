#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

cd "${ROOT_DIR}"

echo "Starting PostgreSQL container..."
docker compose up -d postgres

echo "Applying migrations..."
"${BACKEND_DIR}/scripts/migrate_local_postgres.sh"

cd "${BACKEND_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if [[ -d ".venv" ]]; then
  current_python_version="$({ .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'; } 2>/dev/null || true)"
  if [[ "${current_python_version}" != "3.11" ]]; then
    echo "Recreating backend virtual environment with ${PYTHON_BIN}..."
    rm -rf .venv
  fi
fi

if [[ ! -d ".venv" ]]; then
  echo "Creating backend virtual environment..."
  "${PYTHON_BIN}" -m venv .venv
fi

source .venv/bin/activate

if [[ ! -f ".deps_installed" ]] || [[ requirements.txt -nt .deps_installed ]]; then
  echo "Installing Python dependencies..."
  pip install -r requirements.txt
  touch .deps_installed
fi

echo "Starting FastAPI backend on http://0.0.0.0:8000"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
