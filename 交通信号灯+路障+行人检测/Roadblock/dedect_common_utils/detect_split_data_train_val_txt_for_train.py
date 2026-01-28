import os
import random
import numpy as np


def create_train_val_txt(data_dir, output_dir, train_ratio=0.8, seed=42, check_txt=True):
    """
    创建训练集和验证集的路径列表文件（按子文件夹比例划分）

    参数:
        data_dir: 包含图片的目录
        output_dir: 输出目录
        train_ratio: 训练集比例(0-1)
        seed: 随机种子（确保每次划分结果一致）
        check_txt: 是否检查对应的txt文件是否存在
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 初始化集合
    train_paths = []
    val_paths = []
    total_images = 0
    skipped_images = 0

    # 设置随机种子
    random.seed(seed)
    np.random.seed(seed)

    print("🔍 开始扫描子文件夹...")

    # 遍历所有子文件夹
    for root, dirs, files in os.walk(data_dir):
        # 跳过根目录（只处理子文件夹）
        # if root == data_dir:
        #     continue

        # 获取当前子文件夹的相对路径
        rel_path = os.path.relpath(root, data_dir)
        print(f"  处理子文件夹: {rel_path}")

        # 收集当前文件夹中的有效图片路径
        folder_images = []

        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                img_path = os.path.join(root, file)
                abs_img_path = os.path.abspath(img_path)

                # 检查对应的txt文件是否存在
                if check_txt:
                    base_name = os.path.splitext(file)[0]
                    txt_path = os.path.join(root, f"{base_name}.txt")

                    if os.path.exists(txt_path):
                        folder_images.append(abs_img_path)
                    else:
                        skipped_images += 1
                        print(f"    ⚠️ 跳过无标签的图片: {file}")
                else:
                    folder_images.append(abs_img_path)

        # 统计当前文件夹的图片数量
        num_images = len(folder_images)
        total_images += num_images

        if num_images == 0:
            print(f"    ℹ️ 无有效图片，跳过")
            continue

        # 随机打乱当前文件夹的图片顺序
        random.shuffle(folder_images)

        # 按比例划分当前文件夹的图片
        split_idx = int(num_images * train_ratio)

        # 添加到训练集和验证集
        train_paths.extend(folder_images[:split_idx])
        val_paths.extend(folder_images[split_idx:])

        print(f"    ✅ 添加 {num_images} 张图片: {split_idx} 训练, {num_images - split_idx} 验证")

    # 最终统计
    print("\n📊 数据集最终统计:")
    print(
        f"  扫描子文件夹数: {len([name for name in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, name))])}")
    print(f"  总图片数: {total_images}")
    print(f"  训练集图片数: {len(train_paths)} ({len(train_paths) / total_images:.1%})")
    print(f"  验证集图片数: {len(val_paths)} ({len(val_paths) / total_images:.1%})")

    if skipped_images > 0 and check_txt:
        print(f"⚠️ 警告: 共跳过 {skipped_images} 个无标签的图片")

    # 写入train.txt
    train_txt = os.path.join(output_dir, "train.txt")
    with open(train_txt, 'w') as f:
        for path in train_paths:
            f.write(f"{path}\n")

    # 写入val.txt
    val_txt = os.path.join(output_dir, "val.txt")
    with open(val_txt, 'w') as f:
        for path in val_paths:
            f.write(f"{path}\n")

    print(f"\n✅ 已创建训练集文件: {train_txt}")
    print(f"✅ 已创建验证集文件: {val_txt}")


if __name__ == "__main__":
    # todo ===== 配置参数 =====
    data_dir = r"C:\ai_dataset\detect\lu_zhang\train\images"  # 替换为您的图片目录
    output_dir = r'C:\ai_dataset\detect\lu_zhang\train_txt_file'  # 替换为输出目录
    train_ratio = 0.8  # 训练集比例
    seed = 42  # 随机种子
    check_txt = True  # 是否检查对应的txt文件
    # ===================

    print(f"🚀 开始处理: {data_dir}")
    print(f"随机种子(seed): {seed} - 确保每次划分结果相同")
    print(f"检查标签文件: {'是' if check_txt else '否'}")
    print(f"训练集比例: {train_ratio:.0%} 训练, {1 - train_ratio:.0%} 验证")
    print("按子文件夹比例划分，确保每个子文件夹都有代表样本\n")

    create_train_val_txt(data_dir, output_dir, train_ratio, seed, check_txt)

    print("\n🎉 处理完成!")
    print(f"随机种子说明: 种子值({seed})确保每次运行程序时，")
    print("数据集划分结果相同（可复现性）。如需不同划分，请更改种子值。")