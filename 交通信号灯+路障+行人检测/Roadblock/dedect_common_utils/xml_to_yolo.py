import os
import xml.etree.ElementTree as ET
import argparse
from PIL import Image


def convert_voc_to_yolo(xml_root_dir, image_root_dir, class_names):
    """
    将VOC格式标注转换为YOLO格式txt文件（支持多级目录）

    参数:
        xml_root_dir: VOC XML文件根目录
        image_root_dir: 图片文件根目录
        class_names: 类别名称列表
    """
    # 遍历XML根目录下的所有子目录
    for root, dirs, files in os.walk(xml_root_dir):
        for xml_file in files:
            if not xml_file.endswith('.xml'):
                continue

            xml_path = os.path.join(root, xml_file)
            base_name = os.path.splitext(xml_file)[0]

            try:
                # 计算相对路径（相对于根目录）
                rel_path = os.path.relpath(root, xml_root_dir)

                # 构建对应的图片目录
                if rel_path == '.':
                    current_image_dir = image_root_dir
                else:
                    current_image_dir = os.path.join(image_root_dir, rel_path)

                # 查找图片文件（支持多种格式）
                image_path = None
                for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                    possible_path = os.path.join(current_image_dir, base_name + ext)
                    if os.path.exists(possible_path):
                        image_path = possible_path
                        break

                if not image_path:
                    raise FileNotFoundError(f"未找到匹配的图片文件: {base_name}")

                # 解析XML
                tree = ET.parse(xml_path)
                root_elem = tree.getroot()

                # 获取图片尺寸
                with Image.open(image_path) as img:
                    width, height = img.size

                # todo 准备输出txt路径（与XML同目录）
                # todo labels文件夹路径
                train_dataset_root = os.path.dirname(os.path.normpath(root))
                labels_dir = 'labels'
                labels_path = os.path.join(train_dataset_root, labels_dir)
                if not os.path.exists(labels_path):
                    os.makedirs(labels_path)
                    print(f"'{labels_dir}'目录不存在，已创建")

                txt_path = os.path.join(labels_path, base_name + '.txt')

                with open(txt_path, 'w') as f:
                    for obj in root_elem.findall('object'):
                        # 获取类别名称
                        name = obj.find('name').text.strip()

                        # 跳过未知类别
                        if name not in class_names:
                            print(f"⚠️ 警告: 跳过未知类别 '{name}' in {xml_file}")
                            continue

                        # 获取类别ID
                        class_id = class_names.index(name)

                        # 获取边界框
                        bbox = obj.find('bndbox')
                        xmin = float(bbox.find('xmin').text)
                        ymin = float(bbox.find('ymin').text)
                        xmax = float(bbox.find('xmax').text)
                        ymax = float(bbox.find('ymax').text)

                        # 转换为YOLO格式
                        x_center = (xmin + xmax) / (2.0 * width)
                        y_center = (ymin + ymax) / (2.0 * height)
                        w = (xmax - xmin) / width
                        h = (ymax - ymin) / height

                        # 确保值在[0,1]范围内
                        x_center = max(0, min(1, x_center))
                        y_center = max(0, min(1, y_center))
                        w = max(0, min(1, w))
                        h = max(0, min(1, h))

                        # 写入YOLO格式行
                        f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}\n")

                print(f"✅ 转换成功: {xml_path} -> {txt_path}")

            except Exception as e:
                print(f"❌ 处理 {xml_path} 时出错: {str(e)}")
                # 创建空文件避免后续处理中断
                if 'txt_path' in locals():
                    open(txt_path, 'a').close()


if __name__ == "__main__":
    # TODO 使用说明：支持将xml格式的转yolo格式，支持多级文件夹。xml和图片在同一个文件夹，生成的yolo格式txt与对应xml和图片放一起。
    # todo yolo训练必须要把txt文件放在labels文件夹中。
    # todo 需要定义类别的txt文件（每行一个类别）：作用是定义要转换的类别和顺序。

    parser = argparse.ArgumentParser(description='将VOC格式标注转换为YOLO格式（支持多级目录）')
    parser.add_argument('--xml_root', default=r"C:\ai_dataset\detect\lu_zhang\train\images\road_water", help='VOC XML文件根目录')
    parser.add_argument('--image_root', default=r"C:\ai_dataset\detect\lu_zhang\train\images\road_water", help='图片文件根目录')
    parser.add_argument('--classes', default=r"C:\yolo_model\ultralytics-main\detect_lu_zhang_data_process\lu_zhang.txt", help='类别名称文件路径（每行一个类别）')

    args = parser.parse_args()

    # 读取类别名称
    with open(args.classes, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]

    print(f"类别列表: {', '.join(class_names)}")
    print(f"XML根目录: {args.xml_root}")
    print(f"图片根目录: {args.image_root}")
    print("开始转换...")

    convert_voc_to_yolo(
        xml_root_dir=args.xml_root,
        image_root_dir=args.image_root,
        class_names=class_names
    )

    print("🎉 转换完成！")