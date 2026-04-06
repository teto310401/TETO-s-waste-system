#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（Tkinter版）
"""
import socket
import threading
import struct
import tkinter as tk
from PIL import Image, ImageTk
import io
import time
import queue
import sys

SERVER_IP = "127.0.0.1"  # 修改为服务端IP
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
        self.streaming = True
        self.image_queue = queue.Queue(maxsize=2)
        self.frame_count = 0
        self.last_time = time.time()

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

            self.log("连接成功！")
            return True

        except Exception as e:
            self.log(f"连接失败: {e}")
            return False

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
                        # 清空队列，只保留最新帧
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

            # 解码并显示
            image = Image.open(io.BytesIO(img_data))

            # 获取窗口大小
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            if width > 10 and height > 10:
                # 缩放图像
                img_width, img_height = image.size
                scale = min(width / img_width, height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)

                if scale != 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 显示
            self.current_image = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_image)

            # 隐藏提示
            if hasattr(self, 'info_label') and self.info_label:
                self.info_label.destroy()
                self.info_label = None

            # 显示帧率
            self.frame_count += 1
            if time.time() - self.last_time >= 1.0:
                fps = self.frame_count
                self.root.title(f"Teto 远程控制 - {fps} FPS")
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
        """鼠标移动"""
        if self.video_label and self.current_image:
            # 计算远程坐标
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            img_w = self.current_image.width()
            img_h = self.current_image.height()

            if label_w > 0 and img_w > 0:
                scale_x = img_w / label_w
                scale_y = img_h / label_h

                x = int(event.x * scale_x)
                y = int(event.y * scale_y)

                self.send_command(f"MOVE:{x}:{y}")

    def on_click(self, event):
        """左键点击"""
        self.send_command("CLICK_LEFT")

    def on_right_click(self, event):
        """右键点击"""
        self.send_command("CLICK_RIGHT")

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
        status = tk.Label(self.root, text=f"已连接 - 房间 {self.room}", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)

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

        self.log("GUI已启动")
        self.root.mainloop()

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