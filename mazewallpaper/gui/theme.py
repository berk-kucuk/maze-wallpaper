"""Maze's shared visual language — the palette is Maze Guard's and Maze
Cloak's, so the three windows are indistinguishable side by side. Additions
here are only for things those apps do not have: the gallery, filter chips and
sliders."""
from __future__ import annotations

from mazewallpaper.gui.icons import ensure_control_glyphs

_BASE = """
QWidget {{
    font-size: 13px;
    font-family: "Inter", "Segoe UI", "SF Pro Display", sans-serif;
    color: {text};
}}

QMainWindow, QWidget#root {{ background-color: {bg}; }}

/* ── tabs ─────────────────────────────────────────────────────────────── */
QTabWidget::pane {{ border: none; background-color: {bg}; }}
QTabWidget > QWidget {{ background-color: {bg}; }}
QTabBar {{ background-color: {bg}; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background-color: {bg};
    color: {text_mid};
    padding: 11px 24px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
    font-size: 13px;
}}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {accent}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ color: {text}; }}

/* ── gallery ──────────────────────────────────────────────────────────── */
QListView#gallery {{
    background-color: {bg};
    border: none;
    outline: none;
}}

QLineEdit {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border2};
    border-radius: 6px;
    padding: 7px 12px;
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QLineEdit:hover {{ border-color: {focus}; }}
QLineEdit:focus {{ border-color: {accent}; }}

QPushButton[chip="true"] {{
    background-color: transparent;
    color: {text_mid};
    border: 1px solid {border2};
    border-radius: 15px;
    padding: 5px 14px;
    min-width: 0;
}}
QPushButton[chip="true"]:hover {{ color: {text}; border-color: {focus}; }}
QPushButton[chip="true"]:checked {{
    background-color: {accent};
    color: {accent_text};
    border-color: {accent};
    font-weight: bold;
}}

/* ── inputs ───────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border2};
    border-radius: 6px;
    padding: 6px 12px;
    min-width: 110px;
}}
QComboBox:hover {{ border-color: {focus}; }}
QComboBox:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: right center; width: 22px; border: none; }}
QComboBox QAbstractItemView {{
    background-color: {elevated};
    color: {text};
    border: 1px solid {border2};
    border-radius: 6px;
    selection-background-color: {accent};
    selection-color: {accent_text};
    outline: none;
    padding: 4px;
}}

QSlider::groove:horizontal {{ height: 4px; background: {border2}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {accent};
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {accent_hover}; }}
QSlider:disabled {{ }}
QSlider::sub-page:horizontal:disabled {{ background: {text_dim}; }}
QSlider::handle:horizontal:disabled {{ background: {text_dim}; }}

/* ── checkboxes and radios ────────────────────────────────────────────── */
QCheckBox, QRadioButton {{ color: {text}; spacing: 10px; background: transparent; padding: 2px 0; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {border2};
    background-color: {surface};
}}
QCheckBox::indicator {{ border-radius: 4px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {focus}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{ background-color: {accent}; border-color: {accent}; }}
{glyph_rules}
QCheckBox:disabled, QRadioButton:disabled {{ color: {text_dim}; }}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ border-color: {border}; background-color: {bg}; }}

/* ── buttons ──────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border2};
    border-radius: 6px;
    padding: 7px 16px;
    min-width: 38px;
}}
QPushButton:hover {{ background-color: {elevated}; border-color: {focus}; }}
QPushButton:pressed {{ background-color: {bg}; }}
QPushButton:disabled {{ color: {text_dim}; border-color: {border}; background-color: transparent; }}

QPushButton#primary {{
    background-color: {accent};
    color: {accent_text};
    border-color: {accent};
    font-weight: bold;
    letter-spacing: 1.2px;
    padding: 12px 24px;
    border-radius: 8px;
}}
QPushButton#primary:hover {{ background-color: {accent_hover}; border-color: {accent_hover}; }}
QPushButton#primary:disabled {{ background-color: {elevated}; color: {text_dim}; border-color: {border}; }}

QPushButton#danger:hover {{ border-color: #ff3d00; color: #ff3d00; }}

/* ── scrollbars ───────────────────────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 6px; border: none; margin: 0; }}
QScrollBar::handle:vertical {{ background: {scrollbar}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {focus}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 6px; border: none; }}
QScrollBar::handle:horizontal {{ background: {scrollbar}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; background: none; }}

/* ── structure ────────────────────────────────────────────────────────── */
QLabel {{ background: transparent; }}
QScrollArea {{ background-color: {bg}; border: none; }}
QScrollArea > QWidget > QWidget {{ background-color: {bg}; }}

QWidget#header {{ background-color: {bg}; border-bottom: 1px solid {border}; }}
QLabel#logo {{ color: {text}; font-size: 16px; font-weight: bold; letter-spacing: 4px; }}

QFrame#card {{ background-color: {surface}; border: 1px solid {border}; border-radius: 10px; }}
QFrame#preview_panel {{ background-color: {surface}; border-left: 1px solid {border}; }}
QFrame#preview_box {{ background-color: #000000; border: 1px solid {border2}; border-radius: 10px; }}
QFrame#style_card {{ background-color: {bg}; border: 1px solid {border2}; border-radius: 10px; }}
QFrame#style_card[selected="true"] {{ border: 2px solid {accent}; }}
QFrame#drop_overlay {{ background-color: rgba(0, 0, 0, 200); border: 2px dashed {text_mid}; border-radius: 14px; }}

QLabel#title {{ font-size: 20px; font-weight: bold; letter-spacing: -0.3px; }}
QLabel#big_title {{ font-size: 26px; font-weight: bold; letter-spacing: -0.5px; }}
QLabel#label {{ color: {label}; font-size: 10px; font-weight: bold; letter-spacing: 2px; }}
QLabel#hint {{ color: {text_mid}; font-size: 11px; }}
QLabel#meta {{ color: {text_mid}; font-size: 12px; }}
QLabel#badge {{
    color: {accent_text};
    background-color: {accent};
    border-radius: 4px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}}
QLabel#toast {{
    background-color: {elevated};
    color: {text};
    border: 1px solid {border2};
    border-radius: 8px;
    padding: 9px 16px;
}}

QGroupBox {{
    border: 1px solid {border};
    border-radius: 10px;
    background-color: {surface};
    margin-top: 15px;
    padding: 18px 16px 14px 16px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
    color: {label};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 7px;
    background-color: {bg};
}}

/* ── window chrome ────────────────────────────────────────────────────── */
QPushButton#win_btn, QPushButton#win_close {{
    background: transparent;
    border: none;
    border-radius: 0;
    color: {text_mid};
    font-size: 14px;
    padding: 0;
    min-width: 44px;
    min-height: 44px;
}}
QPushButton#win_btn:hover {{ background-color: {elevated}; color: {text}; }}
QPushButton#win_close:hover {{ background-color: #c42b1c; color: #ffffff; }}

QToolTip {{
    background-color: {elevated};
    color: {text};
    border: 1px solid {border2};
    padding: 6px 9px;
    border-radius: 6px;
}}
"""

DARK = {
    "bg":           "#0a0a0a",
    "surface":      "#111111",
    "elevated":     "#1a1a1a",
    "border":       "#1e1e1e",
    "border2":      "#2e2e2e",
    "focus":        "#4a4a4a",
    "text":         "#f0f0f0",
    "text_mid":     "#9a9a9a",
    "label":        "#8a8a8a",
    "text_dim":     "#4a4a4a",
    "scrollbar":    "#2a2a2a",
    "accent":       "#f0f0f0",
    "accent_text":  "#0a0a0a",
    "accent_hover": "#ffffff",
}

LIGHT = {
    "bg":           "#f5f5f5",
    "surface":      "#ffffff",
    "elevated":     "#ebebeb",
    "border":       "#e2e2e2",
    "border2":      "#d0d0d0",
    "focus":        "#9a9a9a",
    "text":         "#0a0a0a",
    "text_mid":     "#5f5f5f",
    "label":        "#6b6b6b",
    "text_dim":     "#b0b0b0",
    "scrollbar":    "#c8c8c8",
    "accent":       "#0a0a0a",
    "accent_text":  "#f5f5f5",
    "accent_hover": "#282828",
}


def palette(theme: str) -> dict:
    return DARK if theme == "dark" else LIGHT


def _glyph_rules(theme: str, pal: dict) -> str:
    glyphs = ensure_control_glyphs(theme, pal["accent_text"])
    rules = []
    if glyphs.get("check"):
        rules.append(f"QCheckBox::indicator:checked {{ image: url({glyphs['check']}); }}")
    if glyphs.get("dot"):
        rules.append(f"QRadioButton::indicator:checked {{ image: url({glyphs['dot']}); }}")
    return "\n".join(rules)


def get_stylesheet(theme: str) -> str:
    pal = dict(palette(theme))
    pal["glyph_rules"] = _glyph_rules(theme, pal)
    return _BASE.format(**pal)


ACTIVE_COLOR = "#00e676"
