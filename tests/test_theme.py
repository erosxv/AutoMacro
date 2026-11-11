"""O QSS gerado precisa ser válido: um erro de chaves faz o Qt ignorar o tema inteiro."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from automacro.ui.theme import PALETTES, build_qss  # noqa: E402


@pytest.mark.parametrize("theme", sorted(PALETTES))
def test_qss_is_well_formed(theme):
    qss = build_qss(theme)
    assert "{{" not in qss and "}}" not in qss
    assert qss.count("{") == qss.count("}")


@pytest.mark.parametrize("theme", sorted(PALETTES))
def test_qss_is_accepted_by_qt(theme, capfd):
    app = QApplication.instance() or QApplication([])
    widget = QWidget()
    widget.setStyleSheet(build_qss(theme))
    app.processEvents()
    assert "Could not parse" not in capfd.readouterr().err
