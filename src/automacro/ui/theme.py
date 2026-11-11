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
QFrame#banner {{ background: {c['surface2']}; border: 1px solid {c['warning']}; border-radius: 8px; }}
QFrame#updatebar {{ background: {c['surface2']}; border: 1px solid {c['accent']}; border-radius: 8px; }}

QPushButton {{ background: {c['surface2']}; border: 1px solid {c['border']}; border-radius: 8px;
              padding: 7px 14px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['muted']}; background: {c['surface']}; border-color: {c['border']}; }}
QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600;
                      padding: 9px 20px; }}
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
