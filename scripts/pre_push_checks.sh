#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing ${PYTHON_BIN}. Create/activate venv and install dependencies first."
  exit 1
fi

echo "==> Dependency health check"
"${PYTHON_BIN}" -m pip check

echo "==> Ruff lint checks"
"${PYTHON_BIN}" -m ruff check main.py src tests

echo "==> Ruff format checks"
"${PYTHON_BIN}" -m ruff format --check main.py src tests

echo "==> Import/link checks"
"${PYTHON_BIN}" - <<'PY'
import importlib

modules = [
    "src.tools.add_tool",
    "src.tools.subtract_tool",
    "src.tools.multiply_tool",
    "src.tools.gmail.gmail_count",
    "src.tools.gmail.gmail_unread",
    "src.tools.gmail.gmail_draft",
    "src.core.clients.gmail_client",
    "src.core.clients.llm_client",
]

for module_name in modules:
    importlib.import_module(module_name)

print("Import checks passed.")
PY

echo "==> Python syntax checks"
py_files=()
while IFS= read -r file; do
  py_files+=("${file}")
done < <(rg --files -g '*.py' main.py src tests)

if (( ${#py_files[@]} > 0 )); then
  "${PYTHON_BIN}" -m py_compile "${py_files[@]}"
fi

echo "==> Running test suite"
"${PYTHON_BIN}" -m pytest -q
