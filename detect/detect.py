import cv2
import os
import glob
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import threading
import time
from enum import Enum, auto

# =============================================================================
# 0. 高级设置
# =============================================================================
try:
    # 提高Windows系统下的DPI感知，使界面在高分屏上更清晰
    from ctypes import windll

    windll.shcore.SetProcessDpiAwareness(1)
except ImportError:
    pass  # 非Windows系统则跳过

# 1. 模型与配置

# --- 模型路径定义 ---
TRAFFIC_MODEL_PATH = './Traffic/runs/detect/train/weights/best.pt'
OBSTACLE_MODEL_PATH = './Roadblock/lu_zhang_detect/train/weights/best.pt'
LANE_MODEL_PATH = './Lane-and-Vehicle/weights/best.pt'

# --- 类别名称和颜色定义 ---
TRAFFIC_CLASS_NAMES = {0: 'green', 1: 'red', 2: 'yellow', 3: 'go_left'}
TRAFFIC_COLOR_MAP = {
    'green': (0, 255, 0), 'red': (0, 0, 255), 'yellow': (0, 255, 255),
    'go_left': (255, 0, 0), 'unknown': (128, 128, 128)
}
OBSTACLE_CLASS_NAMES = {0: 'obstacle'}
OBSTACLE_COLOR_MAP = {'obstacle': (255, 0, 255), 'unknown': (128, 128, 128)}
# 针对 best.pt (COCO 模型) 更新类别名称。
LANE_CLASS_NAMES = {
    0: 'person', 1: 'bicycle', 2: 'car', 3: 'motorcycle',
    5: 'bus', 7: 'truck', 9: 'traffic light',
}
LANE_COLOR_MAP = {
    'person': (0, 165, 255),  # 橙色用于标记人
    'car': (255, 0, 0),  # 红色用于标记车辆
    'bus': (255, 0, 0),
    'truck': (255, 0, 0),
    'bicycle': (0, 255, 255),
    'motorcycle': (0, 255, 255),
    'traffic light': (0, 255, 255),
    'unknown': (128, 128, 128)
}


# 2. 核心检测逻辑

def load_models():
    """加载所有YOLO模型，并返回模型对象字典"""
    models = {}
    try:
        os.environ['ULTRALYTICS_CHECKS'] = 'False'

        # 检查和加载交通信号灯模型
        if not os.path.exists(TRAFFIC_MODEL_PATH):
            raise FileNotFoundError(f"交通信号灯模型未找到: {TRAFFIC_MODEL_PATH}")
        models['traffic'] = YOLO(TRAFFIC_MODEL_PATH, task='detect')

        # 检查和加载障碍物模型
        if not os.path.exists(OBSTACLE_MODEL_PATH):
            raise FileNotFoundError(f"障碍物模型未找到: {OBSTACLE_MODEL_PATH}")
        models['obstacle'] = YOLO(OBSTACLE_MODEL_PATH, task='detect')

        # 检查和加载车道线/车辆模型
        if not os.path.exists(LANE_MODEL_PATH):
            raise FileNotFoundError(f"车道线模型未找到: {LANE_MODEL_PATH}")
        models['lane'] = YOLO(LANE_MODEL_PATH, task='detect')

        print("所有模型加载成功。")
        return models
    except Exception as e:
        messagebox.showerror("模型加载失败", f"请确保模型文件路径正确。\n错误信息: {str(e)}")
        return None


def draw_detections(image, results, class_names, color_map):
    """在图像上绘制检测框和标签。"""
    if results and results[0].boxes is not None:
        # 提取边界框、置信度和类别ID
        boxes, confs, clss = (
            results[0].boxes.xyxy.cpu().numpy(),
            results[0].boxes.conf.cpu().numpy(),
            results[0].boxes.cls.cpu().numpy()
        )

        for box, conf, cls_id in zip(boxes, confs, clss):
            x1, y1, x2, y2 = map(int, box)

            # 1. 先获取类别名称
            class_name = class_names.get(int(cls_id), 'unknown')
            # 2. 再根据类别名称获取颜色
            color = color_map.get(class_name, color_map.get('unknown'))

            label = f"{class_name} {conf:.2f}"

            # 绘制矩形框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            # 绘制标签
            cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    return image  # 返回绘制后的图像


def process_frame(frame, models):
    """处理视频帧或单张图片。"""
    if frame is None: return None, None
    result_img = frame.copy()

    # 1. 交通信号灯检测
    results_traffic = models['traffic'].predict(source=frame, conf=0.5, verbose=False)
    result_img = draw_detections(result_img, results_traffic, TRAFFIC_CLASS_NAMES, TRAFFIC_COLOR_MAP)

    # 2. 障碍物检测
    results_obstacle = models['obstacle'].predict(source=frame, conf=0.5, verbose=False)
    result_img = draw_detections(result_img, results_obstacle, OBSTACLE_CLASS_NAMES, OBSTACLE_COLOR_MAP)

    # 3. 车道线/通用检测
    results_lane = models['lane'].predict(source=frame, conf=0.5, verbose=False)
    result_img = draw_detections(result_img, results_lane, LANE_CLASS_NAMES, LANE_COLOR_MAP)

    return frame, result_img


def process_image(image_path, models):
    """加载图像并依次运行所有检测模型。"""
    img = cv2.imread(image_path)
    return process_frame(img, models)


# 3. 图形用户界面 (GUI Application)

class ProcessState(Enum):
    IDLE = auto()
    RUNNING_IMAGE_BATCH = auto()
    RUNNING_VIDEO = auto()


class App:
    def __init__(self, root, models):
        self.root = root
        self.models = models
        self.root.title("识别模型 (支持图片批处理与视频实时预览)")
        self.root.geometry("1400x800")
        self.root.minsize(800, 600)

        # --- 状态变量 ---
        self.input_folder, self.output_folder = "", ""
        self.image_paths = []
        self.current_index = -1
        self.process_state = ProcessState.IDLE
        self.processing_thread = None
        self.stop_event = threading.Event()

        # --- 视频实时预览引用的图像对象 (防止垃圾回收) ---
        self.video_tk_img_original = None
        self.video_tk_img_result = None

        # --- Tkinter 风格 ---
        style = ttk.Style()
        style.configure("TButton", padding=8, relief="flat", font=('微软雅黑', 10, 'bold'))
        style.configure("TLabel", padding=5, font=('微软雅黑', 10))

        # --- GUI 布局 (Grid) ---
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        control_frame = ttk.Frame(root, padding="10")
        control_frame.grid(row=0, column=0, sticky="ew")

        image_frame = ttk.Frame(root, padding="0 10 10 10")
        image_frame.grid(row=1, column=0, sticky="nsew")
        image_frame.columnconfigure(0, weight=1)
        image_frame.columnconfigure(1, weight=1)
        image_frame.rowconfigure(0, weight=1)

        self.status_bar = ttk.Label(root, text="准备就绪", relief=tk.SUNKEN, anchor='w')
        self.status_bar.grid(row=2, column=0, sticky="ew")

        # --- 控制按钮 ---
        self.btn_select_folder = ttk.Button(control_frame, text="选择图片文件夹", command=self.select_folder)
        self.btn_select_folder.pack(side=tk.LEFT, padx=10)

        # 图片导航按钮 (修复了缺失的方法引用)
        self.btn_prev = ttk.Button(control_frame, text="< 上一张", command=self.prev_image, state=tk.DISABLED)
        self.btn_prev.pack(side=tk.LEFT, padx=5)
        self.btn_next = ttk.Button(control_frame, text="下一张 >", command=self.next_image, state=tk.DISABLED)
        self.btn_next.pack(side=tk.LEFT, padx=5)

        self.btn_process_control = ttk.Button(control_frame, text="识别所有图片并保存",
                                              command=self.toggle_image_processing,
                                              state=tk.DISABLED)
        self.btn_process_control.pack(side=tk.LEFT, padx=15)

        # 视频按钮
        self.btn_select_video = ttk.Button(control_frame, text="选择视频并实时预览/保存", command=self.select_video)
        self.btn_select_video.pack(side=tk.LEFT, padx=(30, 10))

        # --- 处理速度选项 (仅用于图片批处理显示) ---
        speed_label = ttk.Label(control_frame, text="显示速度:")
        speed_label.pack(side=tk.LEFT, padx=(15, 5))
        self.processing_speed = tk.StringVar(value="快速")
        speed_combobox = ttk.Combobox(control_frame, textvariable=self.processing_speed, values=["快速", "慢速"],
                                      state="readonly", width=8)
        speed_combobox.pack(side=tk.LEFT)

        # --- 图像显示区 ---
        self.panel_original = ttk.Label(image_frame, text="原始图片 / 视频帧", relief=tk.SUNKEN, anchor=tk.CENTER,
                                        background="#f0f0f0")
        self.panel_original.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.panel_result = ttk.Label(image_frame, text="结果图片 / 视频帧 (多模型检测)", relief=tk.SUNKEN,
                                      anchor=tk.CENTER, background="#f0f0f0")
        self.panel_result.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # 绑定 resize 事件
        self.root.bind('<Configure>', self.on_resize)
        self.original_img_cv2 = None
        self.result_img_cv2 = None

    # --- 图片导航方法 (FIX) ---
    def prev_image(self):
        """显示上一张图片"""
        if self.process_state == ProcessState.IDLE and self.current_index > 0:
            self.current_index -= 1
            self.process_single_image_async()

    def next_image(self):
        """显示下一张图片"""
        if self.process_state == ProcessState.IDLE and self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self.process_single_image_async()

    # --- 通用辅助方法 ---

    def on_resize(self, event):
        """窗口大小改变时，重新渲染当前图片以适应新的面板大小"""
        # 仅在IDLE状态且有图片时执行重绘（视频在 worker 中实时绘制）
        if self.process_state == ProcessState.IDLE:
            if self.original_img_cv2 is not None:
                self.show_image_on_panel(self.panel_original, self.original_img_cv2)
            if self.result_img_cv2 is not None:
                self.show_image_on_panel(self.panel_result, self.result_img_cv2)

    def show_image_on_panel(self, panel, cv2_img, is_video=False):
        """将 OpenCV 图像显示到 Tkinter Label 上，并进行缩放适应"""
        # 转换为 RGB 格式，再转为 PIL Image
        img = Image.fromarray(cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB))

        # 获取面板的当前尺寸
        panel_w, panel_h = panel.winfo_width(), panel.winfo_height()
        if panel_w < 50 or panel_h < 50:
            # 初始安全尺寸
            panel_w, panel_h = self.root.winfo_width() // 2 - 20, self.root.winfo_height() - 100

        # 缩略图适应面板
        img.thumbnail((panel_w - 20, panel_h - 20), Image.Resampling.LANCZOS)

        img_tk = ImageTk.PhotoImage(image=img)
        panel.config(image=img_tk, text="")

        # IMPORTANT: 存储引用，防止垃圾回收
        if is_video:
            # 实时视频帧，引用必须存储在类实例变量上
            if panel == self.panel_original:
                self.video_tk_img_original = img_tk
            else:
                self.video_tk_img_result = img_tk
        else:
            # 静态图片，附着在 Label 控件上
            panel.image = img_tk

    def update_gui_panels(self, clear=False):
        """更新图像显示面板"""
        if clear:
            self.panel_original.config(image='', text="原始图片 / 视频帧")
            self.panel_result.config(image='', text="结果图片 / 视频帧 (多模型检测)")
            return

        if self.original_img_cv2 is not None:
            # 静态图片显示
            self.show_image_on_panel(self.panel_original, self.original_img_cv2, is_video=False)
        if self.result_img_cv2 is not None:
            self.show_image_on_panel(self.panel_result, self.result_img_cv2, is_video=False)

    def update_status(self, text):
        self.status_bar.config(text=text)

    def update_button_states(self):
        """更新所有控制按钮的状态"""
        is_idle = self.process_state == ProcessState.IDLE

        # 图片/视频选择按钮
        self.btn_select_folder.config(state=tk.NORMAL if is_idle else tk.DISABLED)

        has_images = bool(self.image_paths)

        # 导航按钮
        can_prev = is_idle and has_images and self.current_index > 0
        can_next = is_idle and has_images and self.current_index < len(self.image_paths) - 1
        self.btn_prev.config(state=tk.NORMAL if can_prev else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if can_next else tk.DISABLED)

        # --- 图片批量处理按钮状态 ---
        if self.process_state == ProcessState.RUNNING_IMAGE_BATCH:
            self.btn_process_control.config(text="暂停 (正在处理...)", command=self.stop_current_process,
                                            state=tk.NORMAL)
        elif is_idle:
            self.btn_process_control.config(text="识别所有图片并保存", command=self.toggle_image_processing,
                                            state=tk.NORMAL if has_images else tk.DISABLED)
        else:
            self.btn_process_control.config(state=tk.DISABLED)

        # --- 视频按钮状态 ---
        if self.process_state == ProcessState.RUNNING_VIDEO:
            self.btn_select_video.config(text="停止视频处理", command=self.stop_current_process, state=tk.NORMAL)
        elif is_idle:
            self.btn_select_video.config(text="选择视频并实时预览/保存", command=self.select_video, state=tk.NORMAL)
        else:
            self.btn_select_video.config(state=tk.DISABLED)

    def stop_current_process(self):
        """通用停止方法，用于停止当前正在运行的线程。"""
        if self.process_state != ProcessState.IDLE:
            self.stop_event.set()
            if self.process_state == ProcessState.RUNNING_IMAGE_BATCH:
                self.btn_process_control.config(text="正在停止...")
            elif self.process_state == ProcessState.RUNNING_VIDEO:
                self.btn_select_video.config(text="正在停止...")

    # --- 图片处理逻辑 (单张/批处理) ---

    def select_folder(self):
        """选择图片文件夹并加载图片列表。"""
        if self.process_state != ProcessState.IDLE: return

        folder = filedialog.askdirectory(title="请选择包含图片的文件夹")
        if not folder: return
        self.input_folder = folder
        self.output_folder = os.path.join(self.input_folder, "output")
        os.makedirs(self.output_folder, exist_ok=True)
        self.image_paths = sorted(glob.glob(os.path.join(self.input_folder, '*.[jJ][pP][gG]')) +
                                  glob.glob(os.path.join(self.input_folder, '*.[pP][nN][gG]')))
        if self.image_paths:
            self.current_index = 0
            self.process_single_image_async()
        else:
            messagebox.showwarning("提示", "文件夹中未找到任何图片 (仅支持 JPG/PNG)。")
            self.current_index = -1
        self.update_button_states()
        self.update_status(f"已加载 {len(self.image_paths)} 张图片，结果将保存到: {self.output_folder}")

    def process_single_image_async(self):
        """异步处理单张图片"""
        if not (0 <= self.current_index < len(self.image_paths)):
            self.update_button_states()  # 确保导航状态正确
            return

        path = self.image_paths[self.current_index]
        self.update_status(f"正在处理: {os.path.basename(path)}...")

        # 禁用导航按钮防止在处理过程中多次点击
        self.btn_prev.config(state=tk.DISABLED)
        self.btn_next.config(state=tk.DISABLED)
        threading.Thread(target=self._single_image_worker, args=(path,), daemon=True).start()

    def _single_image_worker(self, image_path):
        """工作线程：执行单张图像处理和保存"""
        original_img, result_img = process_image(image_path, self.models)
        if result_img is not None:
            # 仅在主线程更新 GUI
            self.root.after(0, self.on_single_image_processed, original_img, result_img)

            # 异步保存图片
            output_path = os.path.join(self.output_folder, os.path.basename(image_path))
            cv2.imwrite(output_path, result_img)
        else:
            self.root.after(0, self.on_single_image_processed, None, None)

    def on_single_image_processed(self, original_img, result_img):
        """在主线程中处理完单张图片后的回调"""
        self.original_img_cv2 = original_img
        self.result_img_cv2 = result_img

        if original_img is not None:
            self.update_gui_panels()
            path = self.image_paths[self.current_index]
            self.update_status(f"显示: {os.path.basename(path)} ({self.current_index + 1}/{len(self.image_paths)})")
        else:
            self.update_gui_panels(clear=True)
            self.update_status(f"图片加载/处理失败")

        # 处理完成后重新启用导航按钮
        self.update_button_states()

    def toggle_image_processing(self):
        """控制图片批量处理的启动/暂停。"""
        if self.process_state == ProcessState.IDLE:
            self.start_processing_all()
        elif self.process_state == ProcessState.RUNNING_IMAGE_BATCH:
            self.stop_current_process()

    def start_processing_all(self):
        if not self.image_paths or self.process_state != ProcessState.IDLE: return

        self.process_state = ProcessState.RUNNING_IMAGE_BATCH
        self.stop_event.clear()
        self.update_button_states()
        self.processing_thread = threading.Thread(target=self._image_batch_worker, daemon=True)
        self.processing_thread.start()

    def _image_batch_worker(self):
        """工作线程：批量处理所有图片"""
        start_index = self.current_index if self.current_index != -1 else 0

        for i in range(start_index, len(self.image_paths)):
            if self.stop_event.is_set(): break

            self.current_index = i
            image_path = self.image_paths[i]

            original_img, result_img = process_image(image_path, self.models)

            if result_img is not None:
                # 实时更新 GUI 和保存文件
                self.original_img_cv2 = original_img
                self.result_img_cv2 = result_img
                self.root.after(0, self.update_gui_panels)

                output_path = os.path.join(self.output_folder, os.path.basename(image_path))
                cv2.imwrite(output_path, result_img)

            status_text = f"处理完成: {os.path.basename(image_path)} ({i + 1}/{len(self.image_paths)})"
            self.root.after(0, self.update_status, status_text)

            if self.processing_speed.get() == '慢速':
                time.sleep(0.75)

        self.root.after(0, self.image_batch_finished)

    def image_batch_finished(self):
        """批量处理结束后的收尾工作"""
        is_stopped = self.stop_event.is_set()

        self.process_state = ProcessState.IDLE
        self.update_button_states()

        if is_stopped:
            self.update_status(f"批量处理已暂停在图片 {self.current_index + 1}。")
        else:
            self.update_status("所有图片处理完毕。结果已保存到 output 文件夹。")

    # --- 视频处理逻辑 (实时预览和保存) ---

    def select_video(self):
        """打开文件对话框选择视频文件，并启动处理。"""
        if self.process_state != ProcessState.IDLE:
            messagebox.showwarning("警告", "当前正在进行其他处理，请稍后再试。")
            return

        video_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4;*.avi;*.mov")]
        )
        if not video_path:
            return

        if not self.output_folder:
            self.output_folder = os.path.join(os.getcwd(), "output")
        os.makedirs(self.output_folder, exist_ok=True)

        self.process_video_async(video_path)

    def process_video_async(self, video_path):
        """异步启动视频处理线程。"""
        self.process_state = ProcessState.RUNNING_VIDEO
        self.stop_event.clear()

        self.update_button_states()
        self.update_status("正在启动视频处理...")

        self.processing_thread = threading.Thread(target=self._video_worker, args=(video_path,), daemon=True)
        self.processing_thread.start()

    def update_video_panels(self, original_img, result_img, current_frame, frame_count, fps, base_name):
        """主线程中更新视频预览面板"""
        # 显示原始帧 (is_video=True ensures proper GC handling)
        self.show_image_on_panel(self.panel_original, original_img, is_video=True)
        # 显示结果帧
        self.show_image_on_panel(self.panel_result, result_img, is_video=True)

        progress = (current_frame / frame_count) * 100
        status_text = (
            f"正在实时预览和保存视频: {base_name} - {progress:.1f}% "
            f"({current_frame}/{frame_count} 帧, 原始FPS: {fps:.1f})"
        )
        self.update_status(status_text)

    def _video_worker(self, video_path):
        """工作线程：处理视频文件，并实时更新 GUI。"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.root.after(0, messagebox.showerror, "错误", "无法打开视频文件。")
            self.root.after(0, self.video_processing_finished, "失败")
            return

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        base_name = os.path.basename(video_path)
        file_name, file_ext = os.path.splitext(base_name)
        # 视频保存路径
        output_video_path = os.path.join(self.output_folder, f"{file_name}_detected{file_ext}")

        # 尝试使用 MP4V 编码器，如果失败则回退到 DIVX 或 XVID
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = None

        try:
            out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
            if not out.isOpened():
                # 尝试 DIVX
                fourcc_divx = cv2.VideoWriter_fourcc(*'DIVX')
                out = cv2.VideoWriter(output_video_path, fourcc_divx, fps, (frame_width, frame_height))
                if not out.isOpened():
                    raise Exception("无法初始化任何可用的视频编码器 (mp4v, DIVX)。")
        except Exception as e:
            cap.release()
            self.root.after(0, messagebox.showerror, "编码器错误",
                            f"无法初始化视频写入器，请确保您安装了必要的视频编解码器 (如 FFmpeg 或 XVID)。\n错误: {str(e)}")
            self.root.after(0, self.video_processing_finished, "失败")
            return

        current_frame = 0

        while cap.isOpened() and not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            original_frame, result_frame = process_frame(frame, self.models)

            # 写入视频文件
            out.write(result_frame)

            # --- 实时预览更新 (调用主线程方法) ---
            # 使用 after(0, ...) 将 GUI 更新任务发送给主线程队列
            self.root.after(0, self.update_video_panels, original_frame.copy(), result_frame.copy(),
                            current_frame + 1, frame_count, fps, base_name)

            current_frame += 1

        cap.release()
        out.release()

        if self.stop_event.is_set():
            self.root.after(0, self.video_processing_finished, "暂停")
        else:
            self.root.after(0, self.video_processing_finished, "完成", output_video_path)

    def video_processing_finished(self, status, output_path=None):
        """视频处理结束后的收尾工作 (在主线程执行)"""

        # 清除视频面板引用并恢复默认文本
        self.video_tk_img_original = None
        self.video_tk_img_result = None
        self.update_gui_panels(clear=True)

        self.process_state = ProcessState.IDLE
        self.update_button_states()  # 恢复按钮状态

        if status == "完成":
            messagebox.showinfo("视频处理完成", f"视频处理已完成并保存到:\n{output_path}")
            self.update_status("视频处理完成。")
        elif status == "暂停":
            messagebox.showwarning("处理已停止", "视频处理已手动停止。")
            self.update_status("视频处理已暂停。")
        elif status == "失败":
            self.update_status("视频处理失败。")


# 4. 程序入口
if __name__ == "__main__":
    print("正在加载YOLOv8模型，请稍候...")
    models = load_models()
    if models:
        root = tk.Tk()
        app = App(root, models)
        root.mainloop()
