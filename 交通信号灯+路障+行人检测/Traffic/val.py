from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO("./runs/detect/train/weights/best.pt")
    model.val(data=r"C:\Users\Administrator\Desktop\yolov8\mydata.yaml",  # 换成自己机器的绝对路径
              batch=32,
              workers=0,
              imgsz=640)