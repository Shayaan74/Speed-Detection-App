from ultralytics import YOLO

DATA_YAML_PATH = "Vehicle-Detection-1/data.yaml"

def main():
    model = YOLO("yolov8s.pt")

    results = model.train(
        data=DATA_YAML_PATH,
        epochs=100,
        imgsz=640,
        batch=16,
        device=0,
        amp=True,
        patience=20,
        project="runs/vehicle_detect",
        name="v1",
        workers=8,
    )

    print("Training complete.")
    print(f"Best weights saved at: runs/vehicle_detect/v1/weights/best.pt")


if __name__ == "__main__":
    main()
