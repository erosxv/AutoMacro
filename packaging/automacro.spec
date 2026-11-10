# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller (modo "onedir": inicia rápido e dispara menos falsos positivos de
# antivírus do que "onefile"). Use build.sh (Linux) ou build.bat (Windows).
import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))


def modules_on_disk(package):
    """Lista todos os módulos de um pacote lendo os arquivos, SEM importá-lo.

    O pynput só importa com um servidor gráfico ativo; durante o build não há um, e
    ``collect_submodules`` falha em silêncio e deixa de fora o backend (win32/xorg).
    """
    spec = importlib.util.find_spec(package)
    names = [package]
    for base in spec.submodule_search_locations:
        for folder, _dirs, files in os.walk(base):
            rel = os.path.relpath(folder, base)
            prefix = package if rel == "." else package + "." + rel.replace(os.sep, ".")
            for fname in files:
                if fname.endswith(".py") and fname != "__init__.py":
                    names.append(prefix + "." + fname[:-3])
            if rel != ".":
                names.append(prefix)
    return names


# O pynput escolhe o backend em tempo de execução, por import dinâmico (invisível ao
# PyInstaller): os submódulos são declarados à mão.
hidden = [m for m in modules_on_disk("pynput") if "darwin" not in m]   # macOS não é alvo
hidden += collect_submodules("automacro")
if sys.platform.startswith("linux"):
    hidden += modules_on_disk("Xlib") + ["evdev"]

# Módulos do Qt que o aplicativo não usa (reduz o tamanho da pasta final).
excludes = [
    "tkinter", "unittest", "pydoc", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtMultimedia",
    "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtSvg",
    "PySide6.QtPdf", "PySide6.Qt3DCore",
]

a = Analysis(
    [os.path.join(ROOT, "packaging", "entry.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoMacro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX aumenta falsos positivos de antivírus
    console=False,      # aplicativo gráfico (sem janela de terminal no Windows)
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AutoMacro",
)
