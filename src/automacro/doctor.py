"""Diagnóstico do ambiente: ``python -m automacro.doctor``.

Verifica Python, dependências, bibliotecas do sistema exigidas pelo Qt, o tipo de sessão
gráfica e o que o backend de entrada consegue (ou não) fazer neste computador. Retorna
código de saída diferente de zero se algo **impeditivo** for encontrado.
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 11)

OK, WARN, FAIL = "[ OK ]", "[AVISO]", "[ERRO]"


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def line(self, tag: str, text: str) -> None:
        if tag == FAIL:
            self.failures += 1
        elif tag == WARN:
            self.warnings += 1
        print(f"{tag} {text}")


def check_python(r: Report) -> None:
    v = sys.version_info
    if (v.major, v.minor) >= MIN_PYTHON:
        r.line(OK, f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        r.line(FAIL, f"Python {v.major}.{v.minor} é antigo demais; é preciso "
                     f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} ou superior.")


def dist_version(dist: str) -> str:
    """Versão instalada do pacote. No executável (PyInstaller) não há metadados de
    instalação: as bibliotecas vêm embutidas, então só confirmamos que existem."""
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        if getattr(sys, "frozen", False):
            return "(embutido no executável)"
        raise


def check_package(r: Report, dist: str, module: str) -> bool:
    try:
        version = dist_version(dist)
    except md.PackageNotFoundError:
        r.line(FAIL, f"{dist} não está instalado (rode o setup novamente).")
        return False
    try:
        importlib.import_module(module)
    except Exception as exc:
        r.line(FAIL, f"{dist} {version} instalado, mas não pôde ser carregado: {exc}")
        return False
    r.line(OK, f"{dist} {version}")
    return True


def check_qt_system_libs(r: Report) -> None:
    """No Linux o plugin 'xcb' do Qt precisa de bibliotecas do sistema (ex.: libxcb-cursor0)."""
    if not sys.platform.startswith("linux"):
        return
    try:
        import PySide6
    except Exception:
        return
    plugin = Path(PySide6.__file__).parent / "Qt" / "plugins" / "platforms" / "libqxcb.so"
    if not plugin.exists() or shutil.which("ldd") is None:
        return
    out = subprocess.run(["ldd", str(plugin)], capture_output=True, text=True).stdout
    missing = sorted({ln.split("=>")[0].strip() for ln in out.splitlines() if "not found" in ln})
    if not missing:
        r.line(OK, "Bibliotecas do sistema exigidas pelo Qt (xcb)")
        return
    r.line(FAIL, "Faltam bibliotecas do sistema para a interface gráfica: " + ", ".join(missing))
    print("        Debian/Ubuntu:  sudo apt install libxcb-cursor0 libxkbcommon-x11-0 "
          "libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 "
          "libxcb-shape0 libxcb-xinerama0 libxcb-xkb1")
    print("        Fedora:         sudo dnf install xcb-util-cursor xcb-util-wm xcb-util-image "
          "xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11")
    print("        Arch:           sudo pacman -S xcb-util-cursor xcb-util-wm xcb-util-image "
          "xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11")


def check_environment(r: Report) -> None:
    from automacro.utils.platform_info import detect_platform

    p = detect_platform()
    r.line(OK, f"Sistema: {p.describe()}")
    if p.is_linux and not p.has_display:
        r.line(WARN, "Nenhuma sessão gráfica detectada (DISPLAY/WAYLAND_DISPLAY vazios): a "
                     "interface e a captura de entrada só funcionam dentro de uma sessão gráfica.")
    if p.is_windows and not p.is_admin:
        r.line(WARN, "Executando sem privilégios de administrador: janelas de programas "
                     "elevados não receberão cliques e teclas simulados.")


def check_backend(r: Report) -> None:
    from automacro.input_handlers.factory import create_backend

    try:
        backend = create_backend()
        caps = backend.capabilities()
    except Exception as exc:
        r.line(FAIL, f"Backend de entrada falhou: {exc}")
        return
    problems = caps.problem_lines()
    if not caps.problems() and not caps.notes:
        r.line(OK, f"Backend de entrada '{caps.backend_name}': todos os recursos disponíveis")
        return
    r.line(WARN, f"Backend de entrada '{caps.backend_name}' com limitações:")
    for text in problems:
        print(f"        - {text}")


def check_paths(r: Report) -> None:
    from automacro.utils.paths import AppPaths

    try:
        paths = AppPaths.default().ensure()
        probe = paths.data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        r.line(OK, f"Pasta de dados gravável: {paths.data_dir}")
    except Exception as exc:
        r.line(FAIL, f"Não foi possível gravar na pasta de dados: {exc}")


def main() -> int:
    print("AutoMacro — diagnóstico do ambiente\n")
    r = Report()
    check_python(r)
    qt_ok = check_package(r, "PySide6-Essentials", "PySide6.QtWidgets")
    # O pynput só pode ser importado com um servidor gráfico; aqui conferimos apenas a
    # instalação. O carregamento real é verificado em check_backend.
    try:
        r.line(OK, f"pynput {dist_version('pynput')}")
    except md.PackageNotFoundError:
        r.line(FAIL, "pynput não está instalado (rode o setup novamente).")
    check_package(r, "platformdirs", "platformdirs")
    if qt_ok:
        check_qt_system_libs(r)
    check_paths(r)
    check_environment(r)
    check_backend(r)
    print()
    if r.failures:
        print(f"Resultado: {r.failures} problema(s) impeditivo(s), {r.warnings} aviso(s).")
        return 1
    print(f"Resultado: ambiente pronto ({r.warnings} aviso(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
