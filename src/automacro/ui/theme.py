"""Temas claro e escuro (QSS)."""

from __future__ import annotations

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#17181c", "surface": "#1e2025", "surface2": "#2b2e35", "border": "#2b2e35",
        "text": "#e8eaed", "muted": "#9aa0a8", "accent": "#4cc2a8", "accent_text": "#0e1f1b",
        "danger": "#e5484d", "success": "#30a46c", "warning": "#f5a524", "info": "#4c9aff",
        "idle": "#4b5263",
    },
    "light": {
        "bg": "#fbfaf7", "surface": "#ffffff", "surface2": "#f1efe9", "border": "#e4e1da",
        "text": "#1f2328", "muted": "#5b616a", "accent": "#1f7a6d", "accent_text": "#ffffff",
        "danger": "#d92d33", "success": "#1f8f58", "warning": "#c77d00", "info": "#2b7de9",
        "idle": "#98a0b3",
    },
}

STATE_COLORS = {
    "idle": "idle", "countdown": "warning", "recording": "danger", "playing": "success",
    "paused": "warning", "autoclicking": "info", "stopping": "idle",
}


def palette(theme: str) -> dict[str, str]:
    return PALETTES.get(theme, PALETTES["dark"])


def build_qss(theme: str) -> str:
    c = palette(theme)
    check_rule = ""
    try:
        from PySide6.QtGui import QGuiApplication

        from automacro.ui.icons import checkmark_file
        # QPixmap sem aplicativo Qt derruba o processo (não é exceção): só desenha com app.
        path = (checkmark_file(c["accent_text"], c["accent"])
                if QGuiApplication.instance() is not None else None)
        if path:
            check_rule = f"QCheckBox::indicator:checked {{ image: url({path}); }}"
    except Exception:       # sem Qt/gráficos (ex.: testes de lógica): segue sem a marca
        pass
    return f"""
* {{ font-size: 14px; }}
QMainWindow, QDialog, QWidget#root {{ background: {c['bg']}; color: {c['text']}; }}
QWidget {{ color: {c['text']}; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 18px; font-weight: 600; }}
QLabel#muted, QLabel[muted="true"] {{ color: {c['muted']}; }}
QLabel#heading {{ font-size: 15px; font-weight: 600; }}
QLabel#bigNumber {{ font-size: 28px; font-weight: 600; }}

QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 10px; background: {c['surface']};
                    top: -1px; }}
QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 9px 18px; margin-right: 2px;
               border: none; border-bottom: 2px solid transparent; font-weight: 500; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover:!selected {{ color: {c['text']}; }}

QFrame#card {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#plainbox {{ background: transparent; border: none; }}
QFrame#banner {{ background: {c['surface2']}; border: none; border-radius: 10px; }}
QPushButton#flat {{ background: transparent; border: none; color: {c['muted']}; padding: 4px 10px; }}
QPushButton#flat:hover {{ color: {c['text']}; }}
QFrame#updatebar {{ background: {c['surface2']}; border: 1px solid {c['accent']}; border-radius: 8px; }}

QPushButton {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 8px;
              padding: 7px 14px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['muted']}; background: {c['surface']}; border-color: {c['border']}; }}
QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600;
                      border-radius: 12px; padding: 11px 22px; }}
QPushButton#primary:hover {{ background: {c['accent']}; }}
QPushButton#primary:disabled {{ background: {c['border']}; color: {c['muted']}; }}
QPushButton#danger {{ background: {c['danger']}; color: white; border: none; font-weight: 700;
                     padding: 8px 16px; }}
QPushButton#danger:hover {{ background: {c['danger']}; border: 2px solid white; padding: 6px 14px; }}
QPushButton#stopall {{ background: {c['text']}; color: {c['bg']}; border: none; font-weight: 600;
                      padding: 8px 16px; }}
QPushButton#stopall:hover {{ background: {c['muted']}; }}
QPushButton#stop {{ background: transparent; border: 1px solid {c['muted']}; color: {c['text']};
                   font-weight: 600; padding: 8px 18px; }}
QPushButton#stop:disabled {{ border-color: {c['border']}; color: {c['muted']}; }}

QFrame#rowlist {{ background: {c['surface']}; border-radius: 16px; }}
QFrame#rowline {{ background: {c['border']}; border: none; margin: 0 14px; }}
QFrame#macrorow {{ background: transparent; border-radius: 12px; }}
QFrame#macrorow:hover {{ background: {c['surface2']}; }}
QLabel#rowname {{ font-size: 15px; font-weight: 500; }}
QLabel#empty {{ color: {c['muted']}; font-size: 15px; }}
QPushButton#play {{ background: transparent; border: 1.5px solid {c['accent']}; border-radius: 22px;
                   padding: 0; }}
QPushButton#play:hover {{ background: {c['surface2']}; }}
QPushButton#play:disabled {{ border-color: {c['border']}; }}
QPushButton#iconbtn {{ background: transparent; border: none; border-radius: 22px; padding: 0; }}
QPushButton#iconbtn:hover {{ background: {c['surface2']}; }}
QPushButton#iconbtn::menu-indicator {{ image: none; width: 0; }}
QFrame#nowbar {{ background: {c['surface2']}; border: none; border-radius: 16px; }}
QLabel#nowtitle {{ font-weight: 500; font-size: 14px; }}
QProgressBar#nowprogress {{ background: {c['border']}; border: none; border-radius: 3px; }}
QProgressBar#nowprogress::chunk {{ background: {c['accent']}; border-radius: 3px; }}
QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 9px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['surface2']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 6px 8px; }}

QFrame#nav {{ background: {c['surface']}; border: none; }}
QLabel#brand {{ font-size: 17px; font-weight: 600; padding: 0 10px 16px 10px; }}
QPushButton#nav {{ background: transparent; border: none; border-radius: 12px; color: {c['muted']};
                  text-align: left; padding: 12px 14px; font-size: 15px; }}
QPushButton#nav:hover {{ color: {c['text']}; }}
QPushButton#nav:checked {{ background: {c['surface2']}; color: {c['text']}; font-weight: 600; }}
QPushButton#nav[compact="true"] {{ text-align: center; padding: 12px 6px; }}
QPushButton#seg {{ background: transparent; border: none; border-radius: 10px; color: {c['muted']};
                  padding: 8px 16px; font-weight: 500; }}
QPushButton#seg:hover {{ color: {c['text']}; }}
QPushButton#seg:checked {{ background: {c['surface2']}; color: {c['text']}; }}
QPushButton:focus {{ outline: none; border: 2px solid {c['accent']}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
  background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 8px;
  min-height: 22px; selection-background-color: {c['accent']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
  border-color: {c['accent']}; }}
/* Spin boxes, combos editáveis e o campo de atalho contêm um QLineEdit interno: sem estas
   regras ele receberia borda e margem em dobro e ficaria espremido (visto no Windows). */
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit, QComboBox QLineEdit {{
  border: none; padding: 0; background: transparent; min-height: 0; }}
/* Sem as setinhas nativas (feias): digita-se o valor; roda do mouse e setas do teclado funcionam.
   (setButtonSymbols(NoButtons) esconde o texto quando há stylesheet; largura zero não.) */
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0; border: none; }}
QKeySequenceEdit {{ background: transparent; border: none; padding: 0; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {c['muted']}; }}
QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']};
  selection-background-color: {c['accent']}; selection-color: white; }}

QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; background: transparent;
  border: 1.5px solid {c['muted']}; }}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background: {c['accent']};
  border-color: {c['accent']}; }}
{check_rule}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ border-color: {c['border']}; }}

QProgressBar {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 6px; height: 12px;
               text-align: center; font-size: 11px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 5px; }}

QTableWidget, QListWidget {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px;
  gridline-color: {c['border']}; alternate-background-color: {c['surface']}; }}
QTableWidget::item:selected, QListWidget::item:selected {{ background: {c['accent']}; color: white; }}
QHeaderView::section {{ background: {c['surface2']}; color: {c['muted']}; border: none;
  border-bottom: 1px solid {c['border']}; padding: 6px 8px; font-weight: 600; }}

QPlainTextEdit {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px; }}
QGroupBox {{ border: 1px solid {c['border']}; border-radius: 10px; margin-top: 14px; padding: 14px 12px 10px 12px;
            background: transparent; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {c['muted']}; }}
QStatusBar {{ background: {c['surface']}; border-top: 1px solid {c['border']}; color: {c['muted']}; }}
QToolTip {{ background: {c['surface2']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
"""
