import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from PIL import Image
import argparse


def convert_yolo_to_voc(image_dir, label_dir, output_dir, class_names):
    """
    将YOLO格式标注转换为VOC格式XML文件

    参数:
        image_dir: 图片所在目录
        label_dir: YOLO标签文件目录
        output_dir: 输出XML文件目录
        class_names: 类别名称列表
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有标签文件
    label_files = [f for f in os.listdir(label_dir) if f.endswith('.txt')]

    for label_file in label_files:
        # 获取对应的图片文件名
        image_name = os.path.splitext(label_file)[0]
        image_path = None

        # 查找图片文件（支持多种格式）
        for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            possible_path = os.path.join(image_dir, image_name + ext)
            if os.path.exists(possible_path):
                image_path = possible_path
                break

        if image_path is None:
            print(f"⚠️ 警告: 找不到图片文件 {image_name}，跳过此标签")
            continue

        try:
            # 获取图片尺寸
            with Image.open(image_path) as img:
                img_width, img_height = img.size

            # 创建XML根元素
            root = ET.Element("annotation")

            # 添加文件夹和文件名
            ET.SubElement(root, "folder").text = os.path.basename(image_dir)
            ET.SubElement(root, "filename").text = os.path.basename(image_path)

            # 添加图片尺寸信息
            size = ET.SubElement(root, "size")
            ET.SubElement(size, "width").text = str(img_width)
            ET.SubElement(size, "height").text = str(img_height)
            ET.SubElement(size, "depth").text = "3"  # 假设RGB图像

            # 添加分割信息（VOC格式要求）
            ET.SubElement(root, "segmented").text = "0"

            # 读取YOLO标签文件
            label_path = os.path.join(label_dir, label_file)
            with open(label_path, 'r') as f:
                lines = f.readlines()

            # 处理每个检测对象
            for line in lines:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue

                # 解析YOLO格式数据
                class_id = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])

                # 转换为绝对坐标
                x_center_abs = x_center * img_width
                y_center_abs = y_center * img_height
                width_abs = width * img_width
                height_abs = height * img_height

                # 计算边界框
                xmin = max(0, int(x_center_abs - width_abs / 2))
                ymin = max(0, int(y_center_abs - height_abs / 2))
                xmax = min(img_width, int(x_center_abs + width_abs / 2))
                ymax = min(img_height, int(y_center_abs + height_abs / 2))

                # 检查边界框有效性
                if xmin >= xmax or ymin >= ymax:
                    print(f"⚠️ 警告: 无效边界框 ({xmin},{ymin},{xmax},{ymax}) in {label_file}")
                    continue

                # 添加对象元素
                obj = ET.SubElement(root, "object")
                ET.SubElement(obj, "name").text = class_names[class_id]
                ET.SubElement(obj, "pose").text = "Unspecified"
                ET.SubElement(obj, "truncated").text = "0"
                ET.SubElement(obj, "difficult").text = "0"

                # 添加边界框
                bndbox = ET.SubElement(obj, "bndbox")
                ET.SubElement(bndbox, "xmin").text = str(xmin)
                ET.SubElement(bndbox, "ymin").text = str(ymin)
                ET.SubElement(bndbox, "xmax").text = str(xmax)
                ET.SubElement(bndbox, "ymax").text = str(ymax)

            # 美化XML格式
            rough_string = ET.tostring(root, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ")

            # 保存XML文件
            xml_path = os.path.join(output_dir, image_name + ".xml")
            with open(xml_path, 'w') as xml_file:
                xml_file.write(pretty_xml)

            print(f"✅ 转换成功: {label_file} -> {os.path.basename(xml_path)}")

        except Exception as e:
            print(f"❌ 处理 {label_file} 时出错: {str(e)}")


if __name__ == "__main__":
    # todo 可用！！！，将yolo格式转为xml格式，目的：查看yolo格式标注是否正确！
    # todo person.txt：该文件用于定义转换0,1数字对应的实际名称
    parser = argparse.ArgumentParser(description='将YOLO格式标注转换为VOC格式XML文件')
    parser.add_argument('--image_dir', default=r"D:\ai_dataset\marknet_1501_person\mk1501-detction\mk1501-detction\test\images", help='图片文件目录')
    parser.add_argument('--label_dir', default=r"D:\ai_dataset\marknet_1501_person\mk1501-detction\mk1501-detction\test\labels", help='YOLO标签文件目录')
    parser.add_argument('--output_dir', default=r"D:\ai_dataset\marknet_1501_person\mk1501-detction\mk1501-detction\test\Annotations", help='输出XML文件目录')
    parser.add_argument('--classes', default=r"D:\ai_model\ultralytics-main\person.txt", help='类别名称文件路径（每行一个类别）')

    args = parser.parse_args()

    # 读取类别名称
    with open(args.classes, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]

    print(f"📋 类别列表: {', '.join(class_names)}")
    print(f"🖼️ 图片目录: {args.image_dir}")
    print(f"🏷️ 标签目录: {args.label_dir}")
    print(f"📂 输出目录: {args.output_dir}")
    print("⏳ 开始转换...")

    convert_yolo_to_voc(
        image_dir=args.image_dir,
        label_dir=args.label_dir,
        output_dir=args.output_dir,
        class_names=class_names
    )

    print("🎉 转换完成！您可以使用labelImg打开生成的XML文件进行验证")