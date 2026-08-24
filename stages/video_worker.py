"""
video_worker.py
Background QThread that runs YOLOv8 + ByteTrack detection/tracking on a
video source, checks vehicle crossings against calibration lines, computes
speed (km/h), and emits fully-annotated frames back to the GUI thread.

"""

import time
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from .calibration_widget import LineData


# ---------------------------------------------------------------------------
# Geometry helpers — classic computational geometry segment-intersection test
# (same "orientation via cross product" idea used in convex hull / CCW checks)
# ---------------------------------------------------------------------------

def _orientation(p: Tuple[float, float], q: Tuple[float, float],
                  r: Tuple[float, float]) -> int:
    """Returns: 0 if collinear, 1 if clockwise, 2 if counterclockwise."""
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else 2


def _on_segment(p: Tuple, q: Tuple, r: Tuple) -> bool:
    """Checks if q lies on segment p-r, given they're already collinear."""
    return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and
            min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))


def segments_intersect(p1: Tuple, p2: Tuple, p3: Tuple, p4: Tuple) -> bool:
    """
    True if segment (p1-p2) intersects segment (p3-p4).
    Used to detect a vehicle's centroid path crossing a calibration line
    between two consecutive frames (frame-to-frame movement = a segment).
    """
    o1, o2 = _orientation(p1, p2, p3), _orientation(p1, p2, p4)
    o3, o4 = _orientation(p3, p4, p1), _orientation(p3, p4, p2)

    if o1 != o2 and o3 != o4:
        return True
    # Collinear edge cases (rare for real vehicle motion, but cheap to cover)
    if o1 == 0 and _on_segment(p1, p3, p2):
        return True
    if o2 == 0 and _on_segment(p1, p4, p2):
        return True
    if o3 == 0 and _on_segment(p3, p1, p4):
        return True
    if o4 == 0 and _on_segment(p3, p2, p4):
        return True
    return False


# ---------------------------------------------------------------------------
# Per-vehicle tracking state
# ---------------------------------------------------------------------------

@dataclass
class VehicleTrack:
    """Tracks one vehicle's crossing history and last known state.
    Analogous to a small record/struct keyed by ByteTrack's track_id."""
    last_centroid: Tuple[float, float]
    crossing_times: Dict[int, float] = field(default_factory=dict)  # line_id -> timestamp
    speed_kmh: Optional[float] = None


class VideoWorker(QThread):
    """
    Runs in a background thread (never touch GUI widgets directly from here —
    all communication back to the main thread happens via Qt signals).
    """

    frame_ready = Signal(QImage)          # annotated frame for display
    speed_detected = Signal(int, float)    # (track_id, speed_kmh) for logging/UI

    def __init__(self, model_path: str, source: Union[int, str],
                 calibration_lines: List[LineData], speed_limit_kmh: float = 60.0,
                 parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.source = source
        self.calibration_lines = sorted(calibration_lines, key=lambda l: l.line_id)
        self.speed_limit_kmh = speed_limit_kmh

        self._running = False
        self._tracks: Dict[int, VehicleTrack] = {}

    def stop(self):
        """Call from the main thread to request a clean shutdown."""
        self._running = False

    def run(self):
        # Import here (not at module top) so this heavy load only happens
        # once the thread actually starts, keeping GUI startup snappy.
        from ultralytics import YOLO

        model = YOLO(self.model_path)
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            print(f"[VideoWorker] Failed to open source: {self.source}")
            return

        # --- FPS throttling setup (video files only) ---
        # Cameras are inherently real-time (cap.read() blocks until the
        # next frame is actually captured), so throttling only matters
        # for video files, where cap.read() returns as fast as decoding
        # allows — often much faster than the GPU can even infer, but the
        # inference step itself can also be *slower* than native FPS on
        # heavier models, so this is a floor, not a hard guarantee.
        is_video_file = isinstance(self.source, str)
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        # Guard against garbage/zero FPS metadata (corrupt files, some codecs)
        if not source_fps or source_fps <= 0:
            source_fps = 30.0
        frame_interval_s = 1.0 / source_fps

        self._running = True
        while self._running:
            loop_start = time.time()

            ret, frame = cap.read()
            if not ret:
                break  # end of video file, or camera disconnected

            # persist=True keeps ByteTrack's internal state alive across
            # calls, so the same vehicle keeps the same track_id frame-to-frame.
            results = model.track(
                frame, persist=True, tracker="bytetrack.yaml",
                conf=0.4, verbose=False, device=0
            )

            self._process_detections(results, frame)
            self._draw_calibration_lines(frame)

            qimg = self._to_qimage(frame)
            self.frame_ready.emit(qimg)

            if is_video_file:
                # Sleep off whatever time is left in this frame's "budget"
                # so playback matches the file's native FPS. If inference
                # already took longer than frame_interval_s, elapsed will
                # exceed it and we simply skip sleeping (can't claw back
                # lost time, but we also don't fall further behind).
                elapsed = time.time() - loop_start
                remaining = frame_interval_s - elapsed
                if remaining > 0:
                    time.sleep(remaining)

        cap.release()

    def _process_detections(self, results, frame: np.ndarray):
        if results[0].boxes.id is None:
            return  # no confirmed tracks this frame (e.g. first few frames)

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy().astype(int)
        now = time.time()

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = box
            centroid = ((x1 + x2) / 2, (y1 + y2) / 2)

            track = self._tracks.get(track_id)
            if track is None:
                # First time seeing this ID — just record position, no crossing check yet.
                self._tracks[track_id] = VehicleTrack(last_centroid=centroid)
            else:
                self._check_line_crossings(track_id, track, centroid, now)
                track.last_centroid = centroid

            self._draw_vehicle_box(frame, box, track_id)

    def _check_line_crossings(self, track_id: int, track: VehicleTrack,
                               current_centroid: Tuple[float, float], now: float):
        prev_centroid = track.last_centroid

        for line in self.calibration_lines:
            if line.line_id in track.crossing_times:
                continue  # already crossed this line — don't double-count

            if segments_intersect(prev_centroid, current_centroid, line.p1, line.p2):
                track.crossing_times[line.line_id] = now
                self._try_compute_speed(track_id, track, line)

    def _try_compute_speed(self, track_id: int, track: VehicleTrack, crossed_line: LineData):
        """Looks at neighboring line IDs (crossed_line.id -1 / +1) to see if
        we now have two consecutive crossings -> can compute speed."""
        for neighbor_id, dist_m in self._neighbor_distances(crossed_line.line_id):
            if neighbor_id in track.crossing_times:
                dt = abs(track.crossing_times[crossed_line.line_id] -
                          track.crossing_times[neighbor_id])
                if dt > 0 and dist_m:
                    speed_ms = dist_m / dt
                    track.speed_kmh = speed_ms * 3.6
                    self.speed_detected.emit(track_id, track.speed_kmh)

    def _neighbor_distances(self, line_id: int):
        """Yields (neighbor_line_id, distance_m) for the lines immediately
        before/after this one, so speed works regardless of travel direction."""
        by_id = {l.line_id: l for l in self.calibration_lines}
        if line_id - 1 in by_id:
            yield line_id - 1, by_id[line_id].distance_from_prev_m
        if line_id + 1 in by_id and by_id[line_id + 1].distance_from_prev_m:
            yield line_id + 1, by_id[line_id + 1].distance_from_prev_m

    def _draw_vehicle_box(self, frame: np.ndarray, box: np.ndarray, track_id: int):
        x1, y1, x2, y2 = box.astype(int)
        track = self._tracks[track_id]

        if track.speed_kmh is not None:
            over_limit = track.speed_kmh > self.speed_limit_kmh
            color = (0, 0, 255) if over_limit else (0, 255, 0)  # BGR: red / green
            label = f"ID {track_id}: {track.speed_kmh:.1f} km/h"
        else:
            color = (0, 255, 255)  # yellow: speed not yet known
            label = f"ID {track_id}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, label, (x1, max(y1 - 10, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    def _draw_calibration_lines(self, frame: np.ndarray):
        """Redraws calibration lines each frame using OpenCV, mirroring the
        color/opacity chosen during calibration (alpha-blended manually,
        since OpenCV has no native per-shape opacity like QGraphicsItem)."""
        overlay = frame.copy()
        for line in self.calibration_lines:
            p1 = tuple(map(int, line.p1))
            p2 = tuple(map(int, line.p2))
            bgr_color = (line.color.blue(), line.color.green(), line.color.red())
            cv2.line(overlay, p1, p2, bgr_color, 3)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, dst=frame)

    def _to_qimage(self, frame: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        # .copy() is essential: QImage doesn't own the numpy buffer's memory,
        # so without copying, the array can be garbage-collected/reused by
        # OpenCV's next frame while Qt still holds a dangling pointer to it.
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
