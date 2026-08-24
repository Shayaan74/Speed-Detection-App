# 🚗 Vehicle Speed Detection Dashboard

A real-time computer vision application that detects, tracks, and estimates the speed of vehicles from a live camera feed or video file — built with **YOLOv8**, **ByteTrack**, and a custom **PySide6** desktop GUI.

Users select a video source, calibrate real-world reference lines directly on a captured frame, and the app automatically detects vehicles, tracks them across frames, and calculates their speed as they cross the calibrated lines — flagging any vehicle over a configurable speed limit.

---

## 🎬 Demo

> _Video demo coming soon._

<!--
Replace this section once your demo is recorded. Example embeds:

[▶️ Watch the demo](link-to-video)

or, for a GIF/screenshot preview:

![Demo](docs/demo.gif)
-->

---

## ✨ Features

- 🎥 **Flexible input** — live webcam feed or pre-recorded video files
- 📐 **Interactive calibration** — draw real-world reference lines directly on the video frame, with configurable color, transparency, and real-world distance (in meters or centimeters)
- 🧠 **YOLOv8 object detection** — fine-tuned/trained model for vehicle detection
- 🔁 **ByteTrack multi-object tracking** — persistent vehicle IDs across frames
- ⚡ **Real-time speed estimation** — computed from calibrated distance and line-crossing timestamps
- 🚨 **Speed limit alerts** — vehicles exceeding the configured limit are visually flagged (red bounding box) and logged
- 🖥️ **Clean, dark-themed desktop UI** — guided multi-stage flow (Source → Calibration → Live Detection)
- 🎮 **GPU-accelerated inference** — optimized for NVIDIA RTX GPUs via CUDA

---

## 🛠️ Tech Stack

| Category               | Tools / Libraries          |
|------------------------|-----------------------------|
| Language               | Python                     |
| Object Detection       | YOLOv8 (Ultralytics)       |
| Object Tracking        | ByteTrack                  |
| Deep Learning Backend  | PyTorch + CUDA             |
| GUI Framework          | PySide6 (Qt for Python)    |
| Image/Video Processing | OpenCV                     |
| Numerical Computing    | NumPy                      |
| Dataset Management     | Roboflow                   |

---

## 🏗️ Application Flow

1. **Source Selector** — pick a webcam or browse for a video file, then capture a reference frame.
2. **Calibration View** — draw at least two lines on the reference frame representing real-world distances (with unit conversion, color, and transparency options).
3. **Live Detection Stage** — runs YOLOv8 + ByteTrack on the source, calculates speed as tracked vehicles cross calibration lines, and logs any that exceed the speed limit.

`Source Selector` → `Calibration View` → `Live Detection Stage`

---

## 📁 Project Structure

```
.
├── main_window.py            # App entry point; stitches all stages together
├── styles.py                 # Centralized dark theme (QSS)
├── requirements.txt
└── stages/
    ├── __init__.py
    ├── source_selector.py        # Stage 1: camera/video source selection
    ├── calibration_widget.py     # Stage 2: interactive line calibration
    ├── live_detection_stage.py   # Stage 3: live YOLOv8 detection + speed log UI
    └── video_worker.py           # Background thread: inference, tracking, speed math
```

---

## ⚙️ Installation

**Requirements:** Python 3.9+, an NVIDIA GPU with CUDA support (recommended)

```bash
git clone https://github.com/your-username/vehicle-speed-detection.git
cd vehicle-speed-detection

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

**`requirements.txt`**

```
ultralytics
opencv-python
numpy
PySide6
torch
```

> 💡 Install PyTorch with the CUDA build matching your GPU driver from [pytorch.org](https://pytorch.org/get-started/locally/) for GPU acceleration.

---

## ▶️ Usage

1. Place your trained YOLOv8 weights (`.pt` file) somewhere accessible.
2. Update the model path in `main_window.py`:

```python
window = MainWindow(
    model_path="path/to/your/best.pt",
    speed_limit_kmh=60.0,
)
```

3. Run the app (from the project root):

```bash
python main_window.py
```

4. Follow the on-screen flow:
   - Select a camera or video file → capture a reference frame
   - Draw at least **2 calibration lines**, entering the real-world distance between them
   - Watch live detection, tracking, and speed estimation in action

---

## 📐 Calibration Notes

- Speed accuracy depends entirely on how precisely the **real-world distance** between calibration lines is measured — measure this in real life (tape measure, known road markings, etc.) before relying on results.
- Distance can be entered in **meters or centimeters** — internally always converted to meters.
- At least **2 lines** are required; more lines allow speed checks across multiple segments.

---

## 🧠 Model Training

The detection model was trained using **[Roboflow](https://roboflow.com/)** for dataset annotation, augmentation, and export, then fine-tuned with **YOLOv8 (Ultralytics)**.

---

## 🚧 Roadmap / Future Improvements

- [ ] CSV/JSON export of speed logs
- [ ] Multi-camera support
- [ ] Automatic distance calibration via reference objects
- [ ] Model quantization for faster edge inference

---

## 👥 Authors

Built by **Shayaan** — 3<sup>rd<sup> year Computer Science student at Queen's University Belfast — and **Denzel** as part of an AI/Vision internship project.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
