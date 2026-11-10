"""Grava a versão do build em src/automacro/__init__.py (usado pelo GitHub Actions)."""

import pathlib
import re
import sys

version = sys.argv[1]
if not re.fullmatch(r"\d+(\.\d+){1,3}", version):
    raise SystemExit(f"versão inválida: {version!r}")
path = pathlib.Path(__file__).resolve().parent.parent / "src" / "automacro" / "__init__.py"
text = path.read_text(encoding="utf-8")
new, count = re.subn(r'__version__ = "[^"]*"', f'__version__ = "{version}"', text)
if count != 1:
    raise SystemExit("não encontrei __version__ em __init__.py")
path.write_text(new, encoding="utf-8")
print(f"versão definida: {version}")
