"""
styles.py
Centralized QSS stylesheet for the whole app. Keeping styling in one file
means every widget stays visually consistent without duplicating style
strings across main_window.py, calibration_widget.py, etc.
"""

DARK_THEME = """
/* ---------- Global defaults ---------- */
QWidget {
    background-color: #1e1f26;
    color: #e6e6e6;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 10.5pt;
}

QMainWindow {
    background-color: #17181d;
}

/* ---------- Labels ---------- */
QLabel {
    color: #e6e6e6;
}

QLabel#headerTitle {
    font-size: 15pt;
    font-weight: 600;
    color: #ffffff;
    padding: 10px 16px;
}

QLabel#headerBar {
    background-color: #2a2c36;
    border-bottom: 2px solid #3d8bfd;
}

/* ---------- Buttons ---------- */
QPushButton {
    background-color: #2f313d;
    color: #e6e6e6;
    border: 1px solid #44475a;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #3a3d4d;
    border: 1px solid #3d8bfd;
}

QPushButton:pressed {
    background-color: #262832;
}

QPushButton:disabled {
    background-color: #232430;
    color: #6b6d78;
    border: 1px solid #33343f;
}

/* Primary action buttons (proceed / finish / capture flows) */
QPushButton#primaryButton {
    background-color: #3d8bfd;
    color: #ffffff;
    border: none;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: #5a9dfd;
}

QPushButton#primaryButton:pressed {
    background-color: #2f6fd0;
}

/* Danger/stop buttons */
QPushButton#dangerButton {
    background-color: #e5484d;
    color: #ffffff;
    border: none;
    font-weight: 600;
}

QPushButton#dangerButton:hover {
    background-color: #f0666a;
}

QPushButton#dangerButton:pressed {
    background-color: #c93338;
}

/* ---------- Group boxes ---------- */
QGroupBox {
    border: 1px solid #3a3c4a;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #3d8bfd;
}

/* ---------- Inputs ---------- */
QComboBox, QDoubleSpinBox {
    background-color: #2a2c36;
    border: 1px solid #44475a;
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 22px;
}

QComboBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #3d8bfd;
}

QComboBox QAbstractItemView {
    background-color: #2a2c36;
    selection-background-color: #3d8bfd;
    border: 1px solid #44475a;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #3a3c4a;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #3d8bfd;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QRadioButton {
    spacing: 8px;
    padding: 4px;
}

QRadioButton::indicator {
    width: 14px;
    height: 14px;
}

/* ---------- Lists ---------- */
QListWidget {
    background-color: #23242e;
    border: 1px solid #3a3c4a;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px 4px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #3d8bfd;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #2f313d;
}

/* ---------- Scrollbars (subtle, not the default clunky Windows look) ---------- */
QScrollBar:vertical {
    background: #1e1f26;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #44475a;
    border-radius: 5px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #3d8bfd;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ---------- Dialogs (LinePropertiesDialog) ---------- */
QDialog {
    background-color: #1e1f26;
}
"""
