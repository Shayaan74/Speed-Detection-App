"""
live_detection_stage.py
Final pipeline stage: displays live YOLOv8+ByteTrack annotated video,
logs over-limit speed events, and lets the user stop the feed cleanly
to restart the whole flow.

Requires: video_worker.py, calibration_widget.py in the same folder.
"""

from typing import List, Optional, Union

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal

from video_worker import VideoWorker
from calibration_widget import LineData


class LiveDetectionStage(QWidget):
    """
    Owns the VideoWorker's full lifecycle: starts it with a source +
    calibration lines, renders annotated frames, logs speed events,
    and shuts it down cleanly on request (critical for QThread safety).
    """

    restart_requested = Signal()  # tells MainWindow to go back to source selection

    def __init__(self, model_path: str, speed_limit_kmh: float = 60.0, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.speed_limit_kmh = speed_limit_kmh
        self.worker: Optional[VideoWorker] = None

        # --- Video display ---
        self.video_label = QLabel("Waiting for video feed...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(800, 450)
        self.video_label.setStyleSheet("background-color: black; color: white;")

        # --- Speed event log ---
        self.speed_log = QListWidget()
        self.speed_log.setMaximumWidth(250)

        self.stop_btn = QPushButton("Stop && Start Over")
        self.stop_btn.clicked.connect(self._on_stop_clicked)

        video_row = QHBoxLayout()
        video_row.addWidget(self.video_label, stretch=3)

        log_col = QVBoxLayout()
        log_col.addWidget(QLabel("Speed Log:"))
        log_col.addWidget(self.speed_log)
        video_row.addLayout(log_col, stretch=1)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(video_row)
        main_layout.addWidget(self.stop_btn)

    def start_processing(self, source: Union[int, str], lines: List[LineData]):
        """Call right after calibration finishes to spin up live detection."""
        self._stop_worker()  # defensive: in case one's somehow already running

        self.speed_log.clear()
        self.video_label.setText("Starting detection...")

        self.worker = VideoWorker(
            model_path=self.model_path,
            source=source,
            calibration_lines=lines,
            speed_limit_kmh=self.speed_limit_kmh,
        )
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.speed_detected.connect(self._on_speed_detected)
        self.worker.start()

    def _on_frame_ready(self, qimg: QImage):
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

    def _on_speed_detected(self, track_id: int, speed_kmh: float):
        over_limit = speed_kmh > self.speed_limit_kmh
        prefix = "OVER LIMIT" if over_limit else "OK"
        item = QListWidgetItem(f"{prefix} | ID {track_id}: {speed_kmh:.1f} km/h")
        if over_limit:
            item.setForeground(Qt.red)
        self.speed_log.addItem(item)
        self.speed_log.scrollToBottom()

    def _on_stop_clicked(self):
        self._stop_worker()
        self.restart_requested.emit()

    def _stop_worker(self):
        """Cleanly shuts down the background thread. ALWAYS call this
        before reusing/destroying this stage — killing a running QThread
        without stop()+wait() causes crashes or the classic
        'QThread: Destroyed while thread is still running' warning."""
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait()  # blocks briefly until run() actually returns
            self.worker.frame_ready.disconnect(self._on_frame_ready)
            self.worker.speed_detected.disconnect(self._on_speed_detected)
            self.worker.deleteLater()
            self.worker = None

    def shutdown(self):
        """Call from MainWindow.closeEvent() to guarantee a clean exit."""
        self._stop_worker()
