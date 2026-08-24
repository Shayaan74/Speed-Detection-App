"""
source_selector.py
PySide6 widget for selecting a camera or video file as the input source,
grabbing a reference frame, and emitting it for calibration.

"""

import sys
import cv2
from typing import Union, Optional

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QRadioButton, QButtonGroup, QFileDialog, QMessageBox,
    QGroupBox
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Signal, Qt


MAX_CAMERAS_TO_PROBE = 5  # scan indices 0..4; adjust if you have more devices


def list_available_cameras(max_index: int = MAX_CAMERAS_TO_PROBE) -> list[int]:
    """
    Probes camera indices to find which ones actually open.
    OpenCV has no direct 'list devices' API, so this brute-force check
    is the standard cross-platform workaround.
    """
    available = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW = faster probe on Windows
        if cap.isOpened():
            available.append(idx)
            cap.release()
    return available


class SourceSelector(QWidget):
    """
    Lets the user choose Camera or Video File, grabs a reference frame,
    and emits (frame, source) where source is an int (camera index)
    or str (file path) — reused later to reopen the same source for
    live processing.
    """

    frame_ready = Signal(object, object)  # (np.ndarray frame, Union[int, str] source)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_source: Optional[Union[int, str]] = None
        self.captured_frame = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # --- Source type toggle ---
        self.camera_radio = QRadioButton("Camera")
        self.file_radio = QRadioButton("Video File")
        self.camera_radio.setChecked(True)
        source_type_group = QButtonGroup(self)
        source_type_group.addButton(self.camera_radio)
        source_type_group.addButton(self.file_radio)
        self.camera_radio.toggled.connect(self._on_source_type_changed)

        type_row = QHBoxLayout()
        type_row.addWidget(self.camera_radio)
        type_row.addWidget(self.file_radio)

        # --- Camera selection group ---
        self.camera_group = QGroupBox("Select Camera")
        cam_layout = QHBoxLayout()
        self.camera_combo = QComboBox()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_cameras)
        cam_layout.addWidget(self.camera_combo)
        cam_layout.addWidget(refresh_btn)
        self.camera_group.setLayout(cam_layout)

        # --- File selection group ---
        self.file_group = QGroupBox("Select Video File")
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(browse_btn)
        self.file_group.setLayout(file_layout)
        self.file_group.setVisible(False)  # camera is default

        # --- Capture button + preview ---
        capture_btn = QPushButton("Capture Reference Frame")
        capture_btn.clicked.connect(self._capture_reference_frame)

        self.preview_label = QLabel("Reference frame will appear here")
        self.preview_label.setMinimumSize(480, 270)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid gray;")

        proceed_btn = QPushButton("Proceed to Calibration")
        proceed_btn.setObjectName("primaryButton")
        proceed_btn.clicked.connect(self._proceed)

        main_layout.addLayout(type_row)
        main_layout.addWidget(self.camera_group)
        main_layout.addWidget(self.file_group)
        main_layout.addWidget(capture_btn)
        main_layout.addWidget(self.preview_label)
        main_layout.addWidget(proceed_btn)

        self._refresh_cameras()

    def _on_source_type_changed(self):
        is_camera = self.camera_radio.isChecked()
        self.camera_group.setVisible(is_camera)
        self.file_group.setVisible(not is_camera)

    def _refresh_cameras(self):
        self.camera_combo.clear()
        cameras = list_available_cameras()
        if not cameras:
            self.camera_combo.addItem("No cameras found", userData=None)
            return
        for idx in cameras:
            self.camera_combo.addItem(f"Camera {idx}", userData=idx)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        if path:
            self.file_path_label.setText(path)

    def _get_current_source(self) -> Optional[Union[int, str]]:
        if self.camera_radio.isChecked():
            return self.camera_combo.currentData()
        else:
            path = self.file_path_label.text()
            return path if path != "No file selected" else None

    def _capture_reference_frame(self):
        source = self._get_current_source()
        if source is None:
            QMessageBox.warning(self, "No source selected",
                                 "Please select a valid camera or video file.")
            return

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            QMessageBox.critical(self, "Error", f"Could not open source: {source}")
            return

        frame = None
        if isinstance(source, int):
            # Camera warm-up: first frame(s) are sometimes black/corrupt
            for _ in range(5):
                ret, frame = cap.read()
                if not ret:
                    frame = None
                    break
        else:
            # Video file: first frame is fine, we'll reopen from 0 later anyway
            ret, frame = cap.read()
            if not ret:
                frame = None

        cap.release()

        if frame is None:
            QMessageBox.critical(self, "Error", "Failed to capture a frame from this source.")
            return

        self.captured_frame = frame
        self.selected_source = source
        self._update_preview(frame)

    def _update_preview(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.preview_label.width(), self.preview_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pixmap)

    def _proceed(self):
        if self.captured_frame is None or self.selected_source is None:
            QMessageBox.warning(self, "No frame captured",
                                 "Please capture a reference frame first.")
            return
        self.frame_ready.emit(self.captured_frame, self.selected_source)


# --- Standalone test harness ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = SourceSelector()
    widget.setWindowTitle("Source Selector Test")
    widget.resize(600, 500)
    widget.frame_ready.connect(
        lambda frame, source: print(
            f"Frame captured! shape={frame.shape}, source={source} ({type(source).__name__})"
        )
    )
    widget.show()
    sys.exit(app.exec())
