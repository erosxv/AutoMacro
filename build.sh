#!/usr/bin/env bash
# Gera o executável do AutoMacro para Linux em dist/AutoMacro/ (PyInstaller, modo onedir).
# Prepara o ambiente sozinho se ainda não existir. É preciso compilar em cada sistema
# operacional: um executável gerado no Linux não roda no Windows (e vice-versa).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import PyInstaller, PySide6, pynput' 2>/dev/null; then
  echo "==> Ambiente incompleto; executando setup.sh primeiro"
  ./setup.sh
fi

echo "==> Gerando o executável (pode levar alguns minutos)"
.venv/bin/python -m PyInstaller --noconfirm --clean \
  --distpath dist --workpath build/pyinstaller packaging/automacro.spec

if [ -x dist/AutoMacro/AutoMacro ]; then
  echo "==> Pronto: dist/AutoMacro/AutoMacro"
  echo "    Distribua a pasta dist/AutoMacro/ inteira (ex.: tar -czf AutoMacro-linux.tar.gz -C dist AutoMacro)."
else
  echo "ERRO: o executável não foi gerado." >&2
  exit 1
fi
