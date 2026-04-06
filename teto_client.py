#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（修复鼠标映射 + 显示鼠标）
"""
import socket
import threading
import struct
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import io
import time
import queue
import sys

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000


class RemoteClient:
    def __init__(self, ip, room_id, port=5000):
        self.ip = ip
        self.room = str(room_id).strip()
        self.port = port
        self.sock = None
        self.root = None
        self.video_label = None
        self.current_image = None
        self.current_photo = None
        self.streaming = True
        self.image_queue = queue.Queue(maxsize=2)
        self.frame_count = 0
        self.last_time = time.time()

        # 鼠标相关
        self.remote_mouse_x = 0
        self.remote_mouse_y = 0
        self.screen_width = 1920  # 远程屏幕宽度
        self.screen_height = 1080  # 远程屏幕高度
        self.display_scale = 1.0  # 显示缩放比例

        # 鼠标样式（画一个十字光标）
        self.mouse_cursor = None

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def connect(self):
        """连接服务器"""
        try:
            self.sock = socket.socket()
            self.sock.settimeout(5)
            self.log(f"连接 {self.ip}:{self.port}...")
            self.sock.connect((self.ip, self.port))

            # 发送房间号
            self.sock.send(self.room.encode())
            response = self.sock.recv(1024).decode()

            if response != "OK":
                self.log(f"连接失败: {response}")
                return False

            # 获取远程屏幕尺寸
            self.sock.send(b"GET_SCREEN_SIZE")
            size_data = self.sock.recv(1024).decode()
            if ":" in size_data:
                self.screen_width, self.screen_height = map(int, size_data.split(":"))
                self.log(f"远程屏幕尺寸: {self.screen_width}x{self.screen_height}")

            self.log("连接成功！")
            return True

        except Exception as e:
            self.log(f"连接失败: {e}")
            return False

    def create_mouse_cursor(self, size=20):
        """创建鼠标光标图像"""
        cursor_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cursor_img)

        # 绘制十字光标
        center = size // 2
        # 水平线
        draw.line([(0, center), (size - 1, center)], fill='white', width=2)
        # 垂直线
        draw.line([(center, 0), (center, size - 1)], fill='white', width=2)
        # 中心点
        draw.ellipse([(center - 2, center - 2), (center + 2, center + 2)], fill='red')
        # 外框
        draw.rectangle([(0, 0), (size - 1, size - 1)], outline='white', width=1)

        return ImageTk.PhotoImage(cursor_img)

    def draw_mouse_on_image(self, image):
        """在图像上绘制鼠标位置"""
        if not self.streaming:
            return image

        # 创建可编辑的图像副本
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        draw = ImageDraw.Draw(image)

        # 计算鼠标在图像上的位置（根据缩放比例）
        img_width, img_height = image.size
        mouse_img_x = int(self.remote_mouse_x * img_width / self.screen_width)
        mouse_img_y = int(self.remote_mouse_y * img_height / self.screen_height)

        # 限制范围
        mouse_img_x = max(0, min(mouse_img_x, img_width - 1))
        mouse_img_y = max(0, min(mouse_img_y, img_height - 1))

        # 绘制鼠标指针（圆形+十字）
        size = max(8, min(20, img_width // 50))  # 动态大小

        # 外圈
        draw.ellipse([(mouse_img_x - size, mouse_img_y - size),
                      (mouse_img_x + size, mouse_img_y + size)],
                     outline='white', width=2)
        # 内圈
        draw.ellipse([(mouse_img_x - size // 2, mouse_img_y - size // 2),
                      (mouse_img_x + size // 2, mouse_img_y + size // 2)],
                     fill='red', outline='white', width=1)
        # 十字线
        draw.line([(mouse_img_x - size, mouse_img_y), (mouse_img_x + size, mouse_img_y)],
                  fill='white', width=2)
        draw.line([(mouse_img_x, mouse_img_y - size), (mouse_img_x, mouse_img_y + size)],
                  fill='white', width=2)

        return image

    def receive_video(self):
        """接收视频流"""
        self.log("开始接收视频...")

        while self.streaming and self.sock:
            try:
                self.sock.settimeout(1.0)

                # 接收图像长度
                len_data = b''
                while len(len_data) < 4:
                    chunk = self.sock.recv(4 - len(len_data))
                    if not chunk:
                        return
                    len_data += chunk

                img_len = struct.unpack('>I', len_data)[0]

                if img_len > 0 and img_len < 10 * 1024 * 1024:
                    # 接收图像数据
                    img_data = b''
                    while len(img_data) < img_len:
                        chunk = self.sock.recv(min(8192, img_len - len(img_data)))
                        if not chunk:
                            break
                        img_data += chunk

                    if len(img_data) == img_len:
                        # 清空队列
                        while not self.image_queue.empty():
                            try:
                                self.image_queue.get_nowait()
                            except:
                                break

                        self.image_queue.put(img_data)

            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"接收错误: {e}")
                break

        self.log("视频接收结束")

    def update_display(self):
        """更新显示（在主线程中运行）"""
        if not self.streaming or not self.root:
            return

        try:
            # 获取最新图像
            try:
                img_data = self.image_queue.get_nowait()
            except queue.Empty:
                self.root.after(33, self.update_display)
                return

            # 解码图像
            image = Image.open(io.BytesIO(img_data))

            # 在图像上绘制鼠标
            image = self.draw_mouse_on_image(image)

            # 获取窗口大小
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            if width > 10 and height > 10:
                # 计算缩放比例
                img_width, img_height = image.size
                scale_w = width / img_width
                scale_h = height / img_height
                self.display_scale = min(scale_w, scale_h)

                new_width = int(img_width * self.display_scale)
                new_height = int(img_height * self.display_scale)

                if self.display_scale != 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 转换为Tkinter格式
            self.current_photo = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_photo)

            # 隐藏提示
            if hasattr(self, 'info_label') and self.info_label:
                self.info_label.destroy()
                self.info_label = None

            # 显示帧率
            self.frame_count += 1
            if time.time() - self.last_time >= 1.0:
                fps = self.frame_count
                self.root.title(f"Teto 远程控制 - {fps} FPS - 远程鼠标: ({self.remote_mouse_x}, {self.remote_mouse_y})")
                self.frame_count = 0
                self.last_time = time.time()

        except Exception as e:
            self.log(f"显示错误: {e}")

        # 继续循环
        self.root.after(33, self.update_display)

    def send_command(self, cmd):
        """发送命令"""
        try:
            if self.sock:
                self.sock.send(cmd.encode())
        except:
            pass

    def on_mouse_move(self, event):
        """鼠标移动 - 修正坐标映射"""
        if self.video_label and self.current_photo:
            # 获取实际显示区域的大小
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()

            # 获取图像的实际大小（显示在label中的大小）
            img_w = self.current_photo.width()
            img_h = self.current_photo.height()

            if label_w > 0 and img_w > 0:
                # 计算图像在label中的偏移（居中显示）
                offset_x = (label_w - img_w) // 2
                offset_y = (label_h - img_h) // 2

                # 计算相对于图像的实际坐标
                rel_x = event.x - offset_x
                rel_y = event.y - offset_y

                # 检查是否在图像范围内
                if 0 <= rel_x < img_w and 0 <= rel_y < img_h:
                    # 映射到远程屏幕坐标
                    remote_x = int(rel_x * self.screen_width / img_w)
                    remote_y = int(rel_y * self.screen_height / img_h)

                    # 限制范围
                    remote_x = max(0, min(remote_x, self.screen_width))
                    remote_y = max(0, min(remote_y, self.screen_height))

                    # 更新远程鼠标位置
                    self.remote_mouse_x = remote_x
                    self.remote_mouse_y = remote_y

                    # 发送移动命令
                    self.send_command(f"MOVE:{remote_x}:{remote_y}")

    def on_click(self, event):
        """左键点击"""
        self.send_command("CLICK_LEFT")
        self.log(f"左键点击 - 远程坐标: ({self.remote_mouse_x}, {self.remote_mouse_y})")

    def on_right_click(self, event):
        """右键点击"""
        self.send_command("CLICK_RIGHT")
        self.log(f"右键点击 - 远程坐标: ({self.remote_mouse_x}, {self.remote_mouse_y})")

    def on_key(self, event):
        """键盘事件"""
        key = event.keysym.lower()
        # 映射特殊键
        key_map = {
            'return': 'enter',
            'backspace': 'backspace',
            'space': 'space',
            'escape': 'esc',
            'up': 'up',
            'down': 'down',
            'left': 'left',
            'right': 'right'
        }
        key = key_map.get(key, key)
        if len(key) == 1 or key in ['enter', 'backspace', 'space', 'esc', 'up', 'down', 'left', 'right']:
            self.send_command(f"KEY:{key}")
            self.log(f"按键: {key}")

    def on_closing(self):
        """关闭窗口"""
        self.log("正在关闭...")
        self.streaming = False
        if self.sock:
            self.sock.close()
        if self.root:
            self.root.destroy()

    def start_gui(self):
        """启动GUI"""
        self.root = tk.Tk()
        self.root.title("Teto 远程控制")
        self.root.geometry("1024x768")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 绑定键盘
        self.root.bind_all("<Key>", self.on_key)

        # 主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 视频标签
        self.video_label = tk.Label(main_frame, bg="#2b2b2b")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 鼠标事件
        self.video_label.bind("<Motion>", self.on_mouse_move)
        self.video_label.bind("<Button-1>", self.on_click)
        self.video_label.bind("<Button-3>", self.on_right_click)

        # 状态栏
        status_frame = tk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = tk.Label(status_frame, text=f"已连接 - 房间 {self.room}",
                                     bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.coord_label = tk.Label(status_frame, text="鼠标: (0, 0)",
                                    bd=1, relief=tk.SUNKEN, anchor=tk.E)
        self.coord_label.pack(side=tk.RIGHT)

        # 提示
        self.info_label = tk.Label(main_frame,
                                   text="等待视频流...\n\n移动鼠标控制远程指针\n点击鼠标进行远程点击",
                                   font=("Arial", 14),
                                   fg="white",
                                   bg="#2b2b2b")
        self.info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 启动接收线程
        recv_thread = threading.Thread(target=self.receive_video, daemon=True)
        recv_thread.start()

        # 启动显示循环
        self.root.after(100, self.update_display)

        # 更新坐标显示
        self.update_coord_display()

        self.log("GUI已启动")
        self.root.mainloop()

    def update_coord_display(self):
        """更新坐标显示"""
        if self.coord_label:
            self.coord_label.config(text=f"远程鼠标: ({self.remote_mouse_x}, {self.remote_mouse_y})")
        if self.root:
            self.root.after(100, self.update_coord_display)

    def run(self):
        """运行"""
        if not self.connect():
            input("按回车键退出...")
            return

        self.start_gui()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("=" * 50)
        print("Teto 远程客户端")
        print("=" * 50)
        print("用法: python teto_client.py IP 房间号 [端口]")
        print("示例: python teto_client.py 192.168.1.100 123456 5000")
        print("=" * 50)
        sys.exit(1)

    ip = sys.argv[1]
    room = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000

    client = RemoteClient(ip, room, port)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n客户端已退出")