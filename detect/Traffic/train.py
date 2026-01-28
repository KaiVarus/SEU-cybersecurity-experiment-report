from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("yolov8s.yaml")
    model.train(data=r"C:\Users\Administrator\Desktop\yolov8\mydata.yaml",
                epochs=150,
                batch=1,
                workers=0,
                imgsz=640)