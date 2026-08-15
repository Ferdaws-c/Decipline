"""
qt_style.py - Centralized styling and QSS for the PyQt6 Decipline rewrite.
"""

from PyQt6.QtGui import QColor, QPalette

# Colors
BG       = "#111113"
PANEL_BG = "#1C1C1E"
CARD_BG  = "#252528"
BORDER   = "#3A3A3C"
AMBER    = "#F59E0B"
GREEN    = "#30D158"
RED      = "#FF453A"
TXT_PRI  = "#F5F5F7"
TXT_SEC  = "#8E8E93"
FONT_UI  = "Segoe UI"

def apply_global_style(app):
    """Applies the dark theme palette and QSS to the QApplication."""
    
    # 1. Qt Palette for standard dialogs/menus
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TXT_PRI))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TXT_PRI))
    palette.setColor(QPalette.ColorRole.Text, QColor(TXT_PRI))
    palette.setColor(QPalette.ColorRole.Button, QColor(CARD_BG))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TXT_PRI))
    palette.setColor(QPalette.ColorRole.Link, QColor(AMBER))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(AMBER))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#111113"))
    app.setPalette(palette)
    
    # 2. Qt Style Sheets (QSS) for specific widgets
    qss = f"""
    QWidget {{
        font-family: "{FONT_UI}";
        font-size: 14px;
        color: {TXT_PRI};
        background-color: {BG};
    }}
    
    /* Headers and panels */
    #HeaderPanel, #ControlPanel {{
        background-color: {PANEL_BG};
    }}
    
    /* Buttons */
    QPushButton {{
        background-color: {CARD_BG};
        color: {TXT_PRI};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {BORDER};
    }}
    QPushButton:pressed {{
        background-color: {PANEL_BG};
    }}
    QPushButton#PrimaryButton {{
        background-color: {AMBER};
        color: #111113;
        font-weight: bold;
        border: none;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: #D97706;
    }}
    QPushButton#DangerButton {{
        background-color: {RED};
        color: white;
        font-weight: bold;
        border: none;
    }}
    QPushButton#DangerButton:hover {{
        background-color: #D70015;
    }}
    
    /* List Widget (Library) */
    QListWidget {{
        background-color: {BG};
        border: none;
        outline: none;
    }}
    QListWidget::item {{
        background-color: {CARD_BG};
        border-radius: 6px;
        margin: 4px;
        padding: 10px;
    }}
    QListWidget::item:selected {{
        background-color: {BORDER};
        border: 1px solid {AMBER};
    }}
    
    /* ScrollBars */
    QScrollBar:vertical {{
        border: none;
        background: {BG};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    
    /* Dialogs */
    QDialog {{
        background-color: {BG};
    }}
    
    /* Inputs */
    QLineEdit, QTextEdit, QSpinBox {{
        background-color: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        min-height: 20px;
        color: {TXT_PRI};
    }}
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {AMBER};
    }}
    """
    app.setStyleSheet(qss)
