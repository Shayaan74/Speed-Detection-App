"""
main_window.py
Stitches SourceSelector -> CalibrationView -> LiveDetectionStage into a
single flowing app using QStackedWidget, with a persistent header showing
the user's current stage.
"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QMessageBox,
    QWidget, QVBoxLayout, QLabel
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtCore import Qt
from typing import List

from source_selector import SourceSelector
from calibration_widget import CalibrationView, LineData
from live_detection_stage import LiveDetectionStage
from styles import DARK_THEME


STAGE_TITLES = {
    0: "Step 1 of 3 — Select Video Source",
    1: "Step 3 of 3 — Live Detection & Speed Monitoring",
    "calibration": "Step 2 of 3 — Draw Calibration Lines",
}


class MainWindow(QMainWindow):
    def __init__(self, model_path: str, speed_limit_kmh: float = 60.0):
        super().__init__()
        self.setWindowTitle("Vehicle Speed Detection Dashboard")
        self.resize(1150, 780)

        # --- Header bar: gives the user a persistent sense of progress ---
        self.header_bar = QWidget()
        self.header_bar.setObjectName("headerBar")
        header_layout = QVBoxLayout(self.header_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_label = QLabel(STAGE_TITLES[0])
        self.header_label.setObjectName("headerTitle")
        self.header_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(self.header_label)

        self.stacked_widget = QStackedWidget()

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.header_bar)
        central_layout.addWidget(self.stacked_widget)
        self.setCentralWidget(central)

        # Stage 1: Source selection
        self.source_selector = SourceSelector()
        self.source_selector.frame_ready.connect(self._on_frame_ready)

        # Stage 2: Calibration (created fresh each time, needs a frame)
        self.calibration_view = None

        # Stage 3: Live detection (created once — loading YOLO is expensive,
        # so we reuse this stage and just call start_processing/_stop_worker)
        self.live_detection_stage = LiveDetectionStage(
            model_path=model_path, speed_limit_kmh=speed_limit_kmh
        )
        self.live_detection_stage.restart_requested.connect(self.restart_flow)

        self.stacked_widget.addWidget(self.source_selector)       # index 0
        self.stacked_widget.addWidget(self.live_detection_stage)  # index 1

        self.stacked_widget.setCurrentWidget(self.source_selector)

        self._current_source = None
        self._current_frame = None

    def _on_frame_ready(self, frame, source):
        self._current_frame = frame
        self._current_source = source

        self.calibration_view = CalibrationView(frame)
        self.calibration_view.calibration_finished.connect(self._on_calibration_finished)

        self.stacked_widget.addWidget(self.calibration_view)
        self.stacked_widget.setCurrentWidget(self.calibration_view)
        self.header_label.setText(STAGE_TITLES["calibration"])

    def _on_calibration_finished(self, lines: List[LineData]):
        if len(lines) < 2:
            QMessageBox.warning(
                self, "Not enough lines",
                "At least 2 lines are needed to calculate speed."
            )
            return

        self.live_detection_stage.start_processing(self._current_source, lines)
        self.stacked_widget.setCurrentWidget(self.live_detection_stage)
        self.header_label.setText(STAGE_TITLES[1])

        self.stacked_widget.removeWidget(self.calibration_view)
        self.calibration_view.deleteLater()
        self.calibration_view = None

    def restart_flow(self):
        self._current_frame = None
        self._current_source = None
        self.stacked_widget.setCurrentWidget(self.source_selector)
        self.header_label.setText(STAGE_TITLES[0])

    def closeEvent(self, event: QCloseEvent):
        self.live_detection_stage.shutdown()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)  # applies to every widget in the app
    window = MainWindow(
        model_path="runs/detect/runs/vehicle_detect/v1/weights/best.pt",
        speed_limit_kmh=60.0,
    )
    window.show()
    sys.exit(app.exec())
