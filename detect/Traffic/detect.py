from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("./runs/detect/train/weights/best.pt")
    results = model.predict(source='./inference/images/', stream=True, show=False, imgsz=640, save=True)

    for result in results:
        print(result.boxes.xyxy)
