"""Temas claro e escuro (QSS)."""

from __future__ import annotations

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#17181c", "surface": "#1e2025", "surface2": "#2b2e35", "border": "#2b2e35",
        "text": "#e8eaed", "muted": "#9aa0a8", "accent": "#4cc2a8", "accent_text": "#0e1f1b",
        "danger": "#e5484d", "success": "#30a46c", "warning": "#f5a524", "info": "#4c9aff",
        "idle": "#4b5263", "line": "#3d424c", "accent_hover": "#62d1b8", "accent_press": "#3fae96",
    },
    "light": {
        "bg": "#fbfaf7", "surface": "#ffffff", "surface2": "#f1efe9", "border": "#e4e1da",
        "text": "#1f2328", "muted": "#5b616a", "accent": "#1f7a6d", "accent_text": "#ffffff",
        "danger": "#d92d33", "success": "#1f8f58", "warning": "#c77d00", "info": "#2b7de9",
        "idle": "#98a0b3", "line": "#cdc9bf", "accent_hover": "#278a7b", "accent_press": "#186a5e",
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
    chevron_rule = ""
    try:
        from PySide6.QtGui import QGuiApplication

        from automacro.ui.icons import checkmark_file, chevron_down_file
        # QPixmap sem aplicativo Qt derruba o processo (não é exceção): só desenha com app.
        path = (checkmark_file(c["accent_text"], c["accent"])
                if QGuiApplication.instance() is not None else None)
        if path:
            check_rule = f"QCheckBox::indicator:checked {{ image: url({path}); }}"
        chevron = (chevron_down_file(c["muted"]) if QGuiApplication.instance() is not None else None)
        if chevron:
            chevron_rule = f"QComboBox::down-arrow {{ image: url({chevron}); width: 16px; height: 16px; }}"
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

/* Botões em três níveis: principal (preenchido), secundário (contorno) e discreto (#flat).
   A borda tem sempre a mesma largura, então hover e foco só mudam de cor: nada se desloca. */
QPushButton {{ background: transparent; color: {c['text']}; border: 1.5px solid {c['line']};
              border-radius: 12px; padding: 10px 18px; min-height: 20px; font-weight: 500; }}
QPushButton:hover {{ background: {c['surface2']}; border-color: {c['muted']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:focus {{ border-color: {c['accent']}; }}
QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; background: transparent; }}
QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: 1.5px solid {c['accent']};
                      font-weight: 600; padding: 10px 22px; }}
QPushButton#primary:hover {{ background: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#primary:pressed {{ background: {c['accent_press']}; border-color: {c['accent_press']}; }}
QPushButton#primary:focus {{ border-color: {c['text']}; }}
QPushButton#primary:disabled {{ background: {c['surface2']}; color: {c['muted']}; border-color: {c['surface2']}; }}
QPushButton#stopall {{ background: {c['text']}; color: {c['bg']}; border: 1.5px solid {c['text']};
                      font-weight: 600; padding: 10px 18px; }}
QPushButton#stopall:hover {{ background: {c['muted']}; border-color: {c['muted']}; }}
QPushButton#stopall:pressed {{ background: {c['line']}; border-color: {c['line']}; }}
QPushButton#stopall:focus {{ border-color: {c['accent']}; }}

QFrame#rowlist {{ background: {c['surface']}; border-radius: 16px; }}
QFrame#rowline {{ background: {c['border']}; border: none; margin: 0 14px; }}
QFrame#macrorow {{ background: transparent; border-radius: 12px; }}
QFrame#macrorow:hover {{ background: {c['surface2']}; }}
QLabel#rowname {{ font-size: 15px; font-weight: 500; }}
QLabel#empty {{ color: {c['muted']}; font-size: 15px; }}
QPushButton#play {{ background: transparent; border: 1.5px solid {c['accent']}; border-radius: 22px;
                   padding: 0; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; }}
QPushButton#play:hover {{ background: {c['surface2']}; }}
QPushButton#play:disabled {{ background: transparent; border: 1.5px solid {c['line']}; border-radius: 22px; }}
QPushButton#iconbtn {{ background: transparent; border: none; border-radius: 22px; padding: 0;
                      min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; }}
QPushButton#iconbtn:hover {{ background: {c['surface2']}; border: none; border-radius: 22px; }}
QPushButton#iconbtn:disabled {{ background: transparent; border: none; border-radius: 22px; }}
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
/* Foco de teclado: o raio precisa ser repetido, senão a borda do foco volta a ser reta. */
QPushButton#nav:focus {{ border: 1.5px solid {c['accent']}; border-radius: 12px; }}
QPushButton#seg:focus {{ border: 1.5px solid {c['accent']}; border-radius: 10px; }}
QPushButton#flat:focus {{ border: 1.5px solid {c['accent']}; border-radius: 10px; }}
QPushButton#iconbtn:focus, QPushButton#play:focus {{ border: 1.5px solid {c['accent']}; border-radius: 22px; }}

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
QComboBox::drop-down {{ border: none; width: 30px; background: transparent; }}
{chevron_rule}
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
