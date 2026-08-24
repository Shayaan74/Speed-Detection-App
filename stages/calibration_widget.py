"""
calibration_widget.py
Standalone-testable PySide6 widget for drawing calibration lines on a
reference frame, with per-line color + transparency + real-world distance.

"""

import sys
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsEllipseItem,
    QDialog, QLabel, QSlider, QDoubleSpinBox, QColorDialog, QFormLayout,
    QDialogButtonBox, QListWidget, QListWidgetItem, QMessageBox, QComboBox
)
from PySide6.QtGui import QPixmap, QImage, QPen, QColor, QBrush
from PySide6.QtCore import Qt, Signal, QPointF, QEvent


@dataclass
class LineData:
    """One calibration line: two points in frame-pixel coordinates,
    plus its visual style and real-world distance context.
    distance_from_prev_m is ALWAYS stored in meters, regardless of
    which unit the user picked in the dialog."""
    line_id: int
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    color: QColor = field(default_factory=lambda: QColor(0, 255, 0))
    opacity: float = 1.0                # 0.0 (invisible) - 1.0 (solid)
    distance_from_prev_m: Optional[float] = None  # meters; None for line 1


class LinePropertiesDialog(QDialog):
    """Popup asking for color, transparency, and distance right after
    a line is drawn. Keeps calibration a tight draw -> configure loop."""

    def __init__(self, is_first_line: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Line")
        self._chosen_color = QColor(0, 255, 0)  # default green

        layout = QFormLayout(self)

        # --- Color picker ---
        self.color_btn = QPushButton()
        self._update_color_btn_style()
        self.color_btn.clicked.connect(self._pick_color)
        layout.addRow("Line Color:", self.color_btn)

        # --- Transparency slider (0 = solid, 90 = almost invisible) ---
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_slider.setRange(0, 90)   # never fully invisible
        self.transparency_slider.setValue(0)       # default: fully solid
        self.transparency_label = QLabel("0%")
        self.transparency_slider.valueChanged.connect(
            lambda v: self.transparency_label.setText(f"{v}%")
        )
        transparency_row = QHBoxLayout()
        transparency_row.addWidget(self.transparency_slider)
        transparency_row.addWidget(self.transparency_label)
        layout.addRow("Transparency:", transparency_row)

        # --- Distance from previous line (skip for the very first line) ---
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.01, 500000.0)
        self.distance_spin.setDecimals(2)
        self.distance_spin.setValue(10.0)
        self.distance_spin.setSuffix(" m")

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["meters (m)", "centimeters (cm)"])
        self.unit_combo.currentIndexChanged.connect(self._on_unit_changed)

        distance_row = QHBoxLayout()
        distance_row.addWidget(self.distance_spin)
        distance_row.addWidget(self.unit_combo)

        if is_first_line:
            self.distance_spin.setEnabled(False)
            self.unit_combo.setEnabled(False)
            layout.addRow("Distance from previous line:",
                          QLabel("N/A (first line)"))
        else:
            layout.addRow("Distance from previous line:", distance_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _pick_color(self):
        color = QColorDialog.getColor(self._chosen_color, self,
                                       "Select Line Color")
        if color.isValid():
            self._chosen_color = color
            self._update_color_btn_style()

    def _update_color_btn_style(self):
        self.color_btn.setStyleSheet(
            f"background-color: {self._chosen_color.name()};"
        )
        self.color_btn.setText(self._chosen_color.name())

    def _on_unit_changed(self, index: int):
        """Purely cosmetic: relabels the spinbox suffix to match the
        selected unit. The value the user typed stays as-is until
        get_values() converts it once, at the very end."""
        suffix = " cm" if index == 1 else " m"
        self.distance_spin.setSuffix(suffix)

    def get_values(self):
        transparency_pct = self.transparency_slider.value()
        opacity = 1.0 - (transparency_pct / 100.0)  # invert for QGraphicsItem.setOpacity

        distance_m = None
        if self.distance_spin.isEnabled():
            raw_value = self.distance_spin.value()
            # index 1 == "centimeters (cm)" -> convert to meters for storage,
            # since VideoWorker's speed math (dist_m / dt) expects meters.
            distance_m = raw_value / 100.0 if self.unit_combo.currentIndex() == 1 else raw_value

        return (
            self._chosen_color,
            opacity,
            distance_m,
        )


class CalibrationView(QWidget):
    """
    Displays a reference frame; user clicks two points to draw a line,
    then configures it via LinePropertiesDialog. Emits calibration_finished
    with the full list of LineData when the user is done.
    """

    calibration_finished = Signal(list)  # List[LineData]

    PREVIEW_COLOR = QColor(255, 255, 0)  # yellow, used only for in-progress dot/line
    DOT_RADIUS = 4

    def __init__(self, frame: np.ndarray, parent=None):
        super().__init__(parent)
        self.frame = frame
        self.lines: List[LineData] = []
        self._pending_point: Optional[QPointF] = None
        self._next_line_id = 1

        # Live preview items while the user is mid-drawing a line
        self._temp_dot: Optional[QGraphicsEllipseItem] = None
        self._temp_line: Optional[QGraphicsLineItem] = None

        # --- Graphics scene setup ---
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self._load_frame_into_scene()

        # Crosshair cursor makes precise point-clicking much easier than
        # the default arrow, and mouse tracking is required to receive
        # MouseMove events even when no button is held down.
        self.view.viewport().setCursor(Qt.CrossCursor)
        self.view.setMouseTracking(True)
        self.view.viewport().setMouseTracking(True)

        # Intercept clicks + moves on the view's viewport
        self.view.viewport().installEventFilter(self)

        # --- Side panel: line list + controls ---
        self.line_list = QListWidget()
        undo_btn = QPushButton("Undo Last Line")
        undo_btn.clicked.connect(self._undo_last_line)
        clear_btn = QPushButton("Clear All Lines")
        clear_btn.clicked.connect(self._clear_all_lines)
        finish_btn = QPushButton("Finish Calibration")
        finish_btn.setObjectName("primaryButton")
        finish_btn.clicked.connect(self._finish_calibration)

        side_panel = QVBoxLayout()
        side_panel.setSpacing(10)
        side_panel.addWidget(QLabel("Calibration Lines:"))
        side_panel.addWidget(self.line_list)
        side_panel.addWidget(undo_btn)
        side_panel.addWidget(clear_btn)
        side_panel.addWidget(finish_btn)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        main_layout.addWidget(self.view, stretch=3)
        side_container = QWidget()
        side_container.setLayout(side_panel)
        main_layout.addWidget(side_container, stretch=1)

    def _load_frame_into_scene(self):
        rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, w, h)

    def eventFilter(self, obj, event):
        """Catches clicks (to place points) and mouse moves (to update
        the live rubber-band preview) on the QGraphicsView viewport."""
        if obj is self.view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                scene_pos = self.view.mapToScene(event.pos())
                self._handle_click(scene_pos)
                return True
            elif event.type() == QEvent.Type.MouseMove:
                if self._pending_point is not None:
                    scene_pos = self.view.mapToScene(event.pos())
                    self._update_temp_preview(scene_pos)
                return False  # let the view still process hover/etc.
        return super().eventFilter(obj, event)

    def _handle_click(self, scene_pos: QPointF):
        if self._pending_point is None:
            # First click: drop a dot and start the live preview line
            self._pending_point = scene_pos
            self._start_temp_preview(scene_pos)
        else:
            # Second click completes the line -> clear preview, open dialog
            p1, p2 = self._pending_point, scene_pos
            self._clear_temp_preview()
            self._pending_point = None
            self._configure_new_line(p1, p2)

    def _start_temp_preview(self, point: QPointF):
        r = self.DOT_RADIUS
        self._temp_dot = QGraphicsEllipseItem(
            point.x() - r, point.y() - r, r * 2, r * 2
        )
        self._temp_dot.setBrush(QBrush(self.PREVIEW_COLOR))
        self._temp_dot.setPen(QPen(Qt.NoPen))
        self.scene.addItem(self._temp_dot)

        self._temp_line = QGraphicsLineItem(
            point.x(), point.y(), point.x(), point.y()
        )
        preview_pen = QPen(self.PREVIEW_COLOR, 2, Qt.DashLine)
        self._temp_line.setPen(preview_pen)
        self.scene.addItem(self._temp_line)

    def _update_temp_preview(self, current_pos: QPointF):
        """Called on every mouse move while a line is mid-draw, so the
        dashed line visually stretches from the dot to the cursor."""
        if self._temp_line is not None and self._pending_point is not None:
            self._temp_line.setLine(
                self._pending_point.x(), self._pending_point.y(),
                current_pos.x(), current_pos.y()
            )

    def _clear_temp_preview(self):
        if self._temp_dot is not None:
            self.scene.removeItem(self._temp_dot)
            self._temp_dot = None
        if self._temp_line is not None:
            self.scene.removeItem(self._temp_line)
            self._temp_line = None

    def _configure_new_line(self, p1: QPointF, p2: QPointF):
        is_first = len(self.lines) == 0
        dialog = LinePropertiesDialog(is_first_line=is_first, parent=self)
        if dialog.exec() == QDialog.Accepted:
            color, opacity, distance = dialog.get_values()
            line_data = LineData(
                line_id=self._next_line_id,
                p1=(p1.x(), p1.y()),
                p2=(p2.x(), p2.y()),
                color=color,
                opacity=opacity,
                distance_from_prev_m=distance,
            )
            self._draw_line_on_scene(line_data)
            self.lines.append(line_data)
            self._next_line_id += 1
            self._refresh_line_list()
        # If cancelled: preview was already cleared above, so nothing
        # extra to clean up — the click sequence simply resets.

    def _draw_line_on_scene(self, line_data: LineData):
        pen = QPen(line_data.color, 3)
        item = QGraphicsLineItem(
            line_data.p1[0], line_data.p1[1],
            line_data.p2[0], line_data.p2[1]
        )
        item.setPen(pen)
        item.setOpacity(line_data.opacity)  # native alpha, no manual blending
        item.setData(0, line_data.line_id)  # tag for later lookup/removal
        self.scene.addItem(item)

    def _refresh_line_list(self):
        self.line_list.clear()
        for ld in self.lines:
            dist_str = f"{ld.distance_from_prev_m:.2f} m" if ld.distance_from_prev_m else "N/A"
            item = QListWidgetItem(
                f"Line {ld.line_id} | Color: {ld.color.name()} | "
                f"Opacity: {ld.opacity:.0%} | Dist from prev: {dist_str}"
            )
            self.line_list.addItem(item)

    def _undo_last_line(self):
        if not self.lines:
            return
        removed = self.lines.pop()
        for item in self.scene.items():
            if isinstance(item, QGraphicsLineItem) and item.data(0) == removed.line_id:
                self.scene.removeItem(item)
                break
        self._refresh_line_list()

    def _clear_all_lines(self):
        for item in list(self.scene.items()):
            if isinstance(item, QGraphicsLineItem) and item.data(0) is not None:
                self.scene.removeItem(item)
        self.lines.clear()
        self._refresh_line_list()

    def _finish_calibration(self):
        if len(self.lines) < 2:
            QMessageBox.warning(
                self, "Not enough lines",
                "Draw at least 2 lines to calculate speed between them."
            )
            return
        self.calibration_finished.emit(self.lines)


# --- Standalone test harness ---
if __name__ == "__main__":
    dummy_frame = np.full((480, 640, 3), 40, dtype=np.uint8)
    cv2.putText(dummy_frame, "Sample Frame - Click to draw lines",
                (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

    app = QApplication(sys.argv)
    widget = CalibrationView(dummy_frame)
    widget.setWindowTitle("Calibration Test")
    widget.resize(900, 600)
    widget.calibration_finished.connect(
        lambda lines: print(f"Calibration done with {len(lines)} lines:", lines)
    )
    widget.show()
    sys.exit(app.exec())
