#!/usr/bin/env bash
# Abre o AutoMacro. Se o ambiente ainda não existir, prepara tudo automaticamente.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import automacro, PySide6, pynput' 2>/dev/null; then
  ./setup.sh
fi
exec .venv/bin/python -m automacro "$@"
