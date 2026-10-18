"""Shared color, typography and surface styles for the desktop interface."""

from PyQt6.QtGui import QColor, QFont, QPalette
from pathlib import Path

BG = "#10131C"
PANEL_BG = "#181D29"
CARD_BG = "#202737"
BORDER = "#2B3447"
ACCENT = "#B6A2FA"
GREEN = "#59D5AE"
AMBER = "#F3BB72"
RED = "#F18798"
TXT_PRI = "#EDF1F9"
TXT_SEC = "#9AA6BD"
FONT_UI = "Segoe UI"


def apply_global_style(app):
    icons = (Path(__file__).resolve().parent.parent / "assets" / "ui").as_posix()
    app.setStyle("Fusion")
    app.setFont(QFont(FONT_UI, 10))
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, TXT_PRI),
        (QPalette.ColorRole.Base, PANEL_BG), (QPalette.ColorRole.AlternateBase, "#1B2130"),
        (QPalette.ColorRole.Text, TXT_PRI), (QPalette.ColorRole.Button, CARD_BG),
        (QPalette.ColorRole.ButtonText, TXT_PRI), (QPalette.ColorRole.Highlight, "#39304F"),
        (QPalette.ColorRole.HighlightedText, TXT_PRI), (QPalette.ColorRole.Link, ACCENT),
        (QPalette.ColorRole.ToolTipBase, CARD_BG), (QPalette.ColorRole.ToolTipText, TXT_PRI),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#68758E"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#68758E"))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QWidget {{ font-family: "{FONT_UI}"; color: {TXT_PRI}; }}
        QMainWindow, QDialog, QWidget#Page {{ background: {BG}; }}
        QLabel {{ background: transparent; border: none; }}
        QLabel#Eyebrow {{ color: {ACCENT}; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
        QLabel#PageTitle {{ font-size: 26px; font-weight: 700; letter-spacing: -0.5px; }}
        QLabel#SectionTitle {{ font-size: 15px; font-weight: 600; }}
        QLabel#Muted {{ color: {TXT_SEC}; font-size: 12px; }}
        QLabel#MetricValue {{ font-size: 25px; font-weight: 600; }}
        QLabel#MetricLabel {{ color: {TXT_SEC}; font-size: 11px; }}
        QLabel#Badge {{ background: #25243B; color: {ACCENT}; border-radius: 10px;
                        padding: 6px 12px; font-size: 11px; font-weight: 600; }}
        QFrame#HeaderPanel {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
        QFrame#SurfaceCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 14px; }}
        QFrame#MetricCard {{ background: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 12px; }}
        QPushButton {{ background: {CARD_BG}; border: 1px solid {BORDER};
                       border-radius: 8px; padding: 9px 14px; font-size: 12px; font-weight: 600; }}
        QPushButton:hover {{ background: #2B3449; border-color: #485570; }}
        QPushButton:pressed {{ background: #141A27; }}
        QPushButton:focus {{ border: 1px solid {ACCENT}; }}
        QPushButton:disabled {{ color: #65728A; background: #1A202D; border-color: #252D3D; }}
        QPushButton#PrimaryButton {{ background: {ACCENT}; color: #191326; border: 1px solid {ACCENT}; }}
        QPushButton#PrimaryButton:hover {{ background: #C8B8FF; border-color: #C8B8FF; }}
        QPushButton#PrimaryButton:pressed {{ background: #A28DDF; }}
        QPushButton#PrimaryButton:disabled {{ background: #39334C; color: #8B80A9; border-color: #39334C; }}
        QPushButton#SuccessButton {{ background: #203D37; color: {GREEN}; border-color: #31564B; }}
        QPushButton#SuccessButton:hover {{ background: #2B4B42; }}
        QPushButton#SuccessButton:disabled {{ background: #192B28; color: #597C70; border-color: #293F38; }}
        QPushButton#DangerButton {{ background: #392730; color: {RED}; border-color: #593543; }}
        QPushButton#DangerButton:hover {{ background: #50313F; }}
        QPushButton#DangerButton:disabled {{ background: #261F29; color: #82616D; border-color: #382936; }}
        QPushButton#QuietButton {{ background: transparent; border-color: transparent; color: {TXT_SEC}; }}
        QPushButton#QuietButton:hover {{ background: {CARD_BG}; color: {TXT_PRI}; }}
        QPushButton[active="true"], QPushButton:checked {{ background: #302B45; border-color: #655782; color: {ACCENT}; }}
        QTabWidget::pane {{ border: none; background: {BG}; }}
        QTabBar {{ background: {BG}; }}
        QTabBar::tab {{ background: transparent; color: {TXT_SEC}; padding: 12px 20px;
                        margin: 8px 2px 0 2px; border-bottom: 2px solid transparent; font-size: 12px; }}
        QTabBar::tab:first {{ margin-left: 22px; }}
        QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
        QTabBar::tab:hover {{ color: {TXT_PRI}; background: #171C29; }}
        QTableView {{ background: {PANEL_BG}; alternate-background-color: #1C2230;
                      border: none; selection-background-color: #302C44;
                      selection-color: {TXT_PRI}; outline: none; font-size: 12px; }}
        QTableView::item {{ padding: 8px; border-bottom: 1px solid #242D3E; }}
        QTableView::item:hover {{ background: #252D40; }}
        QHeaderView {{ background: {PANEL_BG}; }}
        QHeaderView::section {{ background: {PANEL_BG}; color: {TXT_SEC}; border: none;
                               border-bottom: 1px solid {BORDER}; padding: 10px 8px;
                               font-size: 11px; font-weight: 600; }}
        QTableCornerButton::section {{ background: {PANEL_BG}; border: none; }}
        QListWidget {{ background: {PANEL_BG}; border: 1px solid {BORDER};
                       border-radius: 12px; outline: none; padding: 8px; }}
        QListWidget::item {{ background: #202737; border: 1px solid transparent;
                             border-radius: 8px; margin: 4px; padding: 16px; }}
        QListWidget::item:hover {{ background: #283148; }}
        QListWidget::item:selected {{ background: #302B45; border-color: #655782; color: {TXT_PRI}; }}
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {{
            background: #121824; border: 1px solid {BORDER}; border-radius: 8px;
            padding: 8px 10px; min-height: 20px; selection-background-color: #493E67;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border-color: {ACCENT};
        }}
        QLineEdit:disabled, QComboBox:disabled {{ background: #171D2A; color: #7E8BA3; }}
        QComboBox {{ padding-right: 28px; }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox::down-arrow {{ image: url("{icons}/chevron-down.svg"); width: 12px; height: 12px; }}
        QSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right;
                              width: 22px; border: none; background: transparent; }}
        QSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right;
                                width: 22px; border: none; background: transparent; }}
        QSpinBox::up-arrow {{ image: url("{icons}/chevron-up.svg"); width: 12px; height: 12px; }}
        QSpinBox::down-arrow {{ image: url("{icons}/chevron-down.svg"); width: 12px; height: 12px; }}
        QComboBox QAbstractItemView {{ background: {CARD_BG}; color: {TXT_PRI};
                                     selection-background-color: #39304F; padding: 6px;
                                     border: 1px solid {BORDER}; outline: none; }}
        QScrollBar:vertical {{ background: transparent; width: 9px; margin: 4px 0; }}
        QScrollBar::handle:vertical {{ background: #39455D; min-height: 24px; border-radius: 4px; }}
        QScrollBar:horizontal {{ background: transparent; height: 9px; }}
        QScrollBar::handle:horizontal {{ background: #39455D; min-width: 24px; border-radius: 4px; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QProgressBar {{ background: #283144; border: none; border-radius: 3px; max-height: 5px; }}
        QProgressBar::chunk {{ background: {GREEN}; border-radius: 3px; }}
        QMenu {{ background: {PANEL_BG}; border: 1px solid {BORDER}; padding: 6px; }}
        QMenu::item {{ padding: 8px 22px; border-radius: 5px; }}
        QMenu::item:selected {{ background: #302B45; }}
        QToolTip {{ background: {CARD_BG}; color: {TXT_PRI}; border: 1px solid {BORDER}; padding: 6px; }}
        QCheckBox {{ spacing: 8px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid #52617D;
                               border-radius: 4px; background: #121824; }}
        QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url("{icons}/check.svg"); }}
    """)
