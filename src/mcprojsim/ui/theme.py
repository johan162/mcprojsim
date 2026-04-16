"""Earth-tone colour palette and shared style helpers for mcprojsim UI."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Earth-tone palette (all hex strings)
# ---------------------------------------------------------------------------

# Warm neutral backgrounds
COLOUR_BG_WINDOW = "#F5F0E8"  # warm cream — main window
COLOUR_BG_PANEL = "#EDE7D9"         # slightly darker cream — panels / sidebars
COLOUR_BG_CARD = "#FAFAF7"          # near-white — card / form areas
COLOUR_BG_SELECTED = "#C8B99A"      # warm tan — selected row / nav item
COLOUR_BG_HOVER = "#DDD3C0"         # lighter tan — hover state

# Text colours
COLOUR_TEXT_PRIMARY = "#2C2416"     # very dark brown — body text
COLOUR_TEXT_SECONDARY = "#5C5040"   # medium brown — labels / captions
COLOUR_TEXT_PLACEHOLDER = "#A09070"  # muted warm grey — placeholder text
COLOUR_TEXT_LINK = "#5C7A52"        # sage green — links

# Accent colours
COLOUR_ACCENT_GREEN = "#5C7A52"     # sage green — primary action / success
COLOUR_ACCENT_GREEN_HOVER = "#4A6342"
COLOUR_ACCENT_GREEN_DARK = "#3A5033"
COLOUR_ACCENT_AMBER = "#B87333"     # copper/amber — secondary action
COLOUR_ACCENT_AMBER_HOVER = "#9A6028"

# Semantic colours
COLOUR_ERROR = "#8B3A3A"            # brick red — validation errors
COLOUR_ERROR_BG = "#F5E8E8"         # pale rose — error field background
COLOUR_WARNING = "#8B6914"          # dark amber — warnings
COLOUR_WARNING_BG = "#FFF8E8"       # pale amber — warning background
COLOUR_SUCCESS = "#3A6B3A"          # forest green — success messages
COLOUR_SUCCESS_BG = "#EAF4EA"

# Borders and dividers
COLOUR_BORDER = "#C8B99A"           # warm tan — general borders
COLOUR_BORDER_FOCUS = "#5C7A52"     # sage green — focused field border
COLOUR_DIVIDER = "#DDD3C0"          # subtle divider lines

# Toolbar / chrome
COLOUR_TOOLBAR_BG = "#3D3326"       # very dark brown — toolbar background
COLOUR_TOOLBAR_TEXT = "#F5F0E8"     # cream — toolbar text/icons
COLOUR_TOOLBAR_HOVER = "#5C5040"    # medium brown — toolbar button hover

# YAML pane
COLOUR_YAML_BG = "#1E1A14"          # almost black brown — code editor bg
COLOUR_YAML_TEXT = "#D4C9A8"        # warm parchment — code text
COLOUR_YAML_KEY = "#8DB880"         # sage green — YAML keys
COLOUR_YAML_STRING = "#C8A85A"      # amber — string values
COLOUR_YAML_NUMBER = "#88B4C8"      # steel blue — numbers
COLOUR_YAML_BOOL = "#C88AB8"        # muted purple — booleans
COLOUR_YAML_COMMENT = "#7A7060"     # muted grey-brown — comments

# ---------------------------------------------------------------------------
# Shared border-radius and spacing constants
# ---------------------------------------------------------------------------
RADIUS_CARD = 8
RADIUS_BUTTON = 6
RADIUS_INPUT = 5
SPACING_SMALL = 6
SPACING_MEDIUM = 12
SPACING_LARGE = 20

# ---------------------------------------------------------------------------
# Global application stylesheet
# ---------------------------------------------------------------------------

APP_STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {COLOUR_BG_WINDOW};
    color: {COLOUR_TEXT_PRIMARY};
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QMenuBar {{
    background-color: {COLOUR_TOOLBAR_BG};
    color: {COLOUR_TOOLBAR_TEXT};
    spacing: 2px;
    padding: 2px 4px;
}}
QMenuBar::item:selected {{
    background-color: {COLOUR_TOOLBAR_HOVER};
    border-radius: {RADIUS_BUTTON}px;
}}
QMenu {{
    background-color: {COLOUR_BG_CARD};
    color: {COLOUR_TEXT_PRIMARY};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
    padding: 4px 0;
}}
QMenu::item:selected {{
    background-color: {COLOUR_BG_SELECTED};
    border-radius: 4px;
}}
QMenu::separator {{
    height: 1px;
    background: {COLOUR_DIVIDER};
    margin: 4px 8px;
}}

QToolBar {{
    background-color: {COLOUR_TOOLBAR_BG};
    border: none;
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    color: {COLOUR_TOOLBAR_TEXT};
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_BUTTON}px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QToolBar QToolButton:hover {{
    background-color: {COLOUR_TOOLBAR_HOVER};
    border-color: {COLOUR_BORDER};
}}
QToolBar QToolButton:pressed {{
    background-color: {COLOUR_ACCENT_GREEN_DARK};
}}
QToolBar QToolButton#runBtn {{
    background-color: {COLOUR_ACCENT_GREEN};
    color: #FFFFFF;
    font-weight: 600;
    padding: 5px 16px;
}}
QToolBar QToolButton#runBtn:hover {{
    background-color: {COLOUR_ACCENT_GREEN_HOVER};
}}
QToolBar QToolButton#runBtn:disabled {{
    background-color: {COLOUR_TEXT_PLACEHOLDER};
    color: #FFFFFF;
}}

QSplitter::handle {{
    background-color: {COLOUR_DIVIDER};
}}
QSplitter::handle:horizontal {{
    width: 2px;
}}
QSplitter::handle:vertical {{
    height: 2px;
}}

/* Left navigation list */
QListWidget#navList {{
    background-color: {COLOUR_BG_PANEL};
    border: none;
    border-right: 1px solid {COLOUR_BORDER};
    padding: 8px 0;
    font-size: 13px;
}}
QListWidget#navList::item {{
    padding: 10px 16px;
    border-radius: 0;
    color: {COLOUR_TEXT_SECONDARY};
}}
QListWidget#navList::item:selected {{
    background-color: {COLOUR_BG_SELECTED};
    color: {COLOUR_TEXT_PRIMARY};
    font-weight: 600;
}}
QListWidget#navList::item:hover:!selected {{
    background-color: {COLOUR_BG_HOVER};
}}

/* Scroll areas / content panels */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background: {COLOUR_BG_PANEL};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLOUR_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Section header labels */
QLabel#sectionHeader {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: {COLOUR_TEXT_PLACEHOLDER};
    text-transform: uppercase;
    padding: 16px 0 6px 0;
}}

/* Form inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {COLOUR_BG_CARD};
    color: {COLOUR_TEXT_PRIMARY};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 10px;
    selection-background-color: {COLOUR_ACCENT_GREEN};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border-color: {COLOUR_BORDER_FOCUS};
    outline: none;
}}
QLineEdit[invalid="true"], QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] {{
    background-color: {COLOUR_ERROR_BG};
    border-color: {COLOUR_ERROR};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {COLOUR_BG_PANEL};
    color: {COLOUR_TEXT_PLACEHOLDER};
}}
QComboBox {{
    background-color: {COLOUR_BG_CARD};
    color: {COLOUR_TEXT_PRIMARY};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_INPUT}px;
    padding: 6px 10px;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOUR_BG_CARD};
    selection-background-color: {COLOUR_BG_SELECTED};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* Push buttons */
QPushButton {{
    background-color: {COLOUR_BG_CARD};
    color: {COLOUR_TEXT_PRIMARY};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {COLOUR_BG_HOVER};
    border-color: {COLOUR_BORDER_FOCUS};
}}
QPushButton:pressed {{
    background-color: {COLOUR_BG_SELECTED};
}}
QPushButton:disabled {{
    color: {COLOUR_TEXT_PLACEHOLDER};
    border-color: {COLOUR_DIVIDER};
}}
QPushButton[role="primary"] {{
    background-color: {COLOUR_ACCENT_GREEN};
    color: #FFFFFF;
    border-color: {COLOUR_ACCENT_GREEN};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background-color: {COLOUR_ACCENT_GREEN_HOVER};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {COLOUR_DIVIDER};
    border-color: {COLOUR_DIVIDER};
    color: {COLOUR_TEXT_PLACEHOLDER};
}}
QPushButton[role="danger"] {{
    color: {COLOUR_ERROR};
    border-color: {COLOUR_ERROR};
}}

/* Table views */
QTableView {{
    background-color: {COLOUR_BG_CARD};
    alternate-background-color: {COLOUR_BG_WINDOW};
    gridline-color: {COLOUR_DIVIDER};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
    selection-background-color: {COLOUR_BG_SELECTED};
    selection-color: {COLOUR_TEXT_PRIMARY};
    outline: none;
}}
QTableView::item {{
    padding: 6px 10px;
}}
QTableView::item:selected {{
    background-color: {COLOUR_BG_SELECTED};
}}
QHeaderView::section {{
    background-color: {COLOUR_BG_PANEL};
    color: {COLOUR_TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {COLOUR_BORDER};
    border-right: 1px solid {COLOUR_DIVIDER};
    padding: 8px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* Tab widget */
QTabWidget::pane {{
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
    background-color: {COLOUR_BG_CARD};
}}
QTabBar {{
    background-color: {COLOUR_BG_PANEL};
}}
QTabBar::tab {{
    background-color: {COLOUR_BG_PANEL};
    color: {COLOUR_TEXT_SECONDARY};
    border: 1px solid {COLOUR_BORDER};
    border-bottom: none;
    border-top-left-radius: {RADIUS_BUTTON}px;
    border-top-right-radius: {RADIUS_BUTTON}px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background-color: {COLOUR_BG_CARD};
    color: {COLOUR_TEXT_PRIMARY};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background-color: {COLOUR_BG_HOVER};
}}

/* Group boxes */
QGroupBox {{
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
    margin-top: 20px;
    padding: 12px;
    font-weight: 600;
    color: {COLOUR_TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    left: 12px;
    top: -11px;
    background-color: {COLOUR_BG_WINDOW};
}}

/* Result card (results pane sections) */
QFrame#resultCard {{
    background-color: {COLOUR_BG_CARD};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_CARD}px;
}}

/* YAML preview */
QPlainTextEdit#yamlEditor {{
    background-color: {COLOUR_YAML_BG};
    color: {COLOUR_YAML_TEXT};
    border: none;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
}}

/* Progress bar */
QProgressBar {{
    background-color: {COLOUR_BG_PANEL};
    border: 1px solid {COLOUR_BORDER};
    border-radius: {RADIUS_BUTTON}px;
    text-align: center;
    color: {COLOUR_TEXT_PRIMARY};
    height: 20px;
}}
QProgressBar::chunk {{
    background-color: {COLOUR_ACCENT_GREEN};
    border-radius: {RADIUS_BUTTON}px;
}}

/* Status bar */
QStatusBar {{
    background-color: {COLOUR_BG_PANEL};
    color: {COLOUR_TEXT_SECONDARY};
    border-top: 1px solid {COLOUR_BORDER};
    font-size: 12px;
    padding: 2px 8px;
}}

/* Checkbox */
QCheckBox {{
    color: {COLOUR_TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOUR_BORDER};
    border-radius: 3px;
    background: {COLOUR_BG_CARD};
}}
QCheckBox::indicator:checked {{
    background-color: {COLOUR_ACCENT_GREEN};
    border-color: {COLOUR_ACCENT_GREEN};
}}

/* Label info/hint styling */
QLabel#hintLabel {{
    color: {COLOUR_TEXT_PLACEHOLDER};
    font-size: 12px;
    font-style: italic;
}}
QLabel#statValue {{
    background-color: transparent;
}}
QLabel#errorLabel {{
    color: {COLOUR_ERROR};
    font-size: 12px;
}}
QLabel#successLabel {{
    color: {COLOUR_SUCCESS};
    font-size: 12px;
    font-weight: 600;
}}
"""
