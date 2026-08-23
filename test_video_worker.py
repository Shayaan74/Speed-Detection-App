"""
test_video_worker.py
Standalone sanity check: does the trained model detect + track vehicles
on a live feed? No GUI wiring, no calibration flow — just proof it works.
"""

import sys
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap, QColor

from video_worker import VideoWorker
from calibration_widget import LineData

app = QApplication(sys.argv)

label = QLabel()
label.setWindowTitle("VideoWorker Test")
label.resize(960, 540)
label.show()

'''worker = VideoWorker(
    model_path="runs/detect/runs/vehicle_detect/v1/weights/best.pt",   # <- your trained weights, exactly as you gave it
    source=0,                             # 0 = default webcam; swap for "some_video.mp4" to test on file instead
    calibration_lines=[
        LineData(line_id=1, p1=(100, 300), p2=(500, 300),
                  color=QColor(0, 255, 0), opacity=1.0, distance_from_prev_m=None),
        LineData(line_id=2, p1=(100, 400), p2=(500, 400),
                  color=QColor(255, 0, 0), opacity=1.0, distance_from_prev_m=10.0),
    ],
    speed_limit_kmh=60.0,
)'''

worker = VideoWorker(
    model_path="runs/detect/runs/vehicle_detect/v1/weights/best.pt",  # your confirmed path
    source="test/test-1.mp4",   # <-- path to your video file instead of 0
    calibration_lines=[
        LineData(line_id=1, p1=(100, 300), p2=(500, 300),
                  color=QColor(0, 255, 0), opacity=1.0, distance_from_prev_m=None),
        LineData(line_id=2, p1=(100, 400), p2=(500, 400),
                  color=QColor(255, 0, 0), opacity=1.0, distance_from_prev_m=10.0),
    ],
    speed_limit_kmh=60.0,
)


worker.frame_ready.connect(lambda qimg: label.setPixmap(QPixmap.fromImage(qimg)))
worker.speed_detected.connect(lambda tid, spd: print(f"Vehicle {tid}: {spd:.1f} km/h"))

worker.start()
sys.exit(app.exec())
