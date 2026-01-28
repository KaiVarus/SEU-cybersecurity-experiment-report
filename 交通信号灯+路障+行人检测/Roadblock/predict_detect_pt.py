from ultralytics import YOLO
import cv2
import os

# 加载模型
model = YOLO(r"C:\yolo_model\ultralytics-main\lu_zhang_detect\train\weights\best.pt")

# 定义路径
source = r"C:\ai_dataset\detect\test_images"
output_dir = r"C:\ai_dataset\detect\predict_results"

# 创建输出目录
os.makedirs(output_dir, exist_ok=True)

# 运行推理
results = model(source, stream=True)

# 处理每个结果
for i, result in enumerate(results):
    # 获取带检测框的图像
    result_img = result.plot()  # 返回带检测框的numpy数组

    # 获取原始文件名
    original_filename = os.path.basename(result.path)

    # 构建输出路径
    output_path = os.path.join(output_dir, original_filename)

    # 保存图像
    cv2.imwrite(output_path, result_img)
    print(f"保存结果: {output_path}")

print(f"所有结果已保存到: {output_dir}")