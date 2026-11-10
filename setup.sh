#!/usr/bin/env bash
# Prepara tudo para rodar o AutoMacro no Linux: cria o ambiente virtual (.venv), instala
# TODAS as dependências e roda o diagnóstico. Pode ser executado quantas vezes quiser.
#
#   ./setup.sh                        instala e verifica
#   ./setup.sh --install-system-deps  também instala as bibliotecas gráficas que o Qt exige
#                                     (pede sua senha via sudo; apt, dnf ou pacman)
# Nenhum compilador é necessário: todas as dependências Python vêm prontas (wheels).
set -euo pipefail
cd "$(dirname "$0")"

INSTALL_SYSTEM_DEPS=0
for arg in "$@"; do
  [ "$arg" = "--install-system-deps" ] && INSTALL_SYSTEM_DEPS=1
done

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mERRO:\033[0m %s\n' "$*" >&2; exit 1; }

# 1) Python 3.11 ou superior ---------------------------------------------------------
PY=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.11 ou superior não encontrado.
  Debian/Ubuntu: sudo apt install python3 python3-venv python3-pip
  Fedora:        sudo dnf install python3
  Arch:          sudo pacman -S python"
say "Usando $($PY --version) ($(command -v $PY))"

# 2) Pacotes do sistema (opcional) -----------------------------------------------------
if [ "$INSTALL_SYSTEM_DEPS" = "1" ]; then
  say "Instalando bibliotecas do sistema exigidas pelo Qt"
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y python3-venv libegl1 libgl1 libxcb-cursor0 \
      libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
      libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y mesa-libEGL mesa-libGL xcb-util-cursor xcb-util-wm xcb-util-image \
      xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm libglvnd xcb-util-cursor xcb-util-wm \
      xcb-util-image xcb-util-keysyms xcb-util-renderutil libxkbcommon-x11
  else
    echo "Gerenciador de pacotes não reconhecido; instale manualmente o que o diagnóstico indicar."
  fi
fi

# 3) Ambiente virtual ----------------------------------------------------------------
if [ -x .venv/bin/python ] && ! .venv/bin/python -c 'import sys' 2>/dev/null; then
  say "Ambiente virtual quebrado; recriando"; rm -rf .venv
fi
if [ ! -x .venv/bin/python ]; then
  say "Criando ambiente virtual (.venv)"
  "$PY" -m venv .venv 2>/dev/null || fail "Não consegui criar o ambiente virtual.
  No Debian/Ubuntu instale:  sudo apt install python3-venv   (ou rode ./setup.sh --install-system-deps)"
fi

# 4) Dependências --------------------------------------------------------------------
say "Instalando dependências (pode levar alguns minutos na primeira vez)"
.venv/bin/python -m pip install --quiet --upgrade pip
if ! .venv/bin/python -m pip install --quiet -r requirements-dev.txt; then
  fail "Falha ao instalar as dependências. Verifique sua conexão com a internet e tente de novo."
fi
# pynput sem as dependências declaradas: no Linux ele puxaria o "evdev", que precisa de
# compilador e só serve a um backend que não usamos (ver comentário em requirements.txt).
.venv/bin/python -m pip install --quiet --no-deps "pynput>=1.7.7" \
  || fail "Falha ao instalar o pynput. Verifique sua conexão com a internet."
.venv/bin/python -m pip install --quiet --no-deps -e .

# 5) Diagnóstico ---------------------------------------------------------------------
say "Verificando o ambiente"
if .venv/bin/python -m automacro.doctor; then
  say "Tudo pronto. Para abrir o aplicativo:  ./run.sh"
  exit 0
fi
echo
# Se o problema são as bibliotecas gráficas do sistema e há um terminal, oferece instalar.
if [ "$INSTALL_SYSTEM_DEPS" = "0" ] && [ -t 0 ] && [ -t 1 ]; then
  printf 'Instalar agora as bibliotecas do sistema que faltam (usa sudo)? [S/n] '
  read -r answer || answer="n"
  case "${answer:-S}" in
    [sSyY]*) exec "$0" --install-system-deps ;;
  esac
fi
echo "O diagnóstico encontrou problemas (acima). Se faltam bibliotecas do sistema, rode:"
echo "  ./setup.sh --install-system-deps"
exit 1
