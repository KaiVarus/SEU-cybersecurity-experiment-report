from ultralytics import YOLO
def train():
    # Load a model
    model = YOLO(r"C:\yolo_model\ultralytics-main\ultralytics\cfg\models\11\yolo11s.yaml")  # build a new model from YAML
# model = YOLO("yolo11n.pt")  # load a pretrained model (recommended for training)
# model = YOLO("yolo11n.yaml").load("yolo11n.pt")  # build from YAML and transfer weights


# Train the model
    results = model.train(data=r"C:\yolo_model\ultralytics-main\ultralytics\cfg\datasets\lu_zhang.yaml", epochs=250, imgsz=640,batch=32,project="lu_zhang_detect")  # todo 这里是数据集路径
if __name__ == '__main__':
    train()
    #freeze_support()