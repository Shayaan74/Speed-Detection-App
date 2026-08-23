"""
train_vehicle_model.py
Trains YOLOv8 on the downloaded Roboflow single-class 'vehicle' dataset.
Optimized for RTX 4080 (8GB+ VRAM laptop GPU).
"""

from ultralytics import YOLO

# --- Point directly at the already-downloaded dataset's data.yaml ---
DATA_YAML_PATH = "Vehicle-Detection-1/data.yaml"  # adjust if your folder name differs

def main():
    model = YOLO("yolov8s.pt")  # small model: good speed/accuracy balance for real-time

    results = model.train(
        data=DATA_YAML_PATH,
        epochs=100,
        imgsz=640,
        batch=16,        # safe for RTX 4080 8GB at imgsz=640; drop to 8 if OOM
        device=0,        # GPU index 0
        amp=True,        # mixed precision -> faster training, lower VRAM use
        patience=20,     # early stopping if no val improvement for 20 epochs
        project="runs/vehicle_detect",
        name="v1",
        workers=8,       # dataloader parallelism; tune to your CPU core count
    )

    print("Training complete.")
    print(f"Best weights saved at: runs/vehicle_detect/v1/weights/best.pt")


if __name__ == "__main__":
    main()
