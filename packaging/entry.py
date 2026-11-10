"""Ponto de entrada usado pelo PyInstaller (o pacote ``automacro`` fica em ``src/``)."""

import sys

from automacro.main import main

if __name__ == "__main__":
    sys.exit(main())
