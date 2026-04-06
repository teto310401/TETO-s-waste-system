#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（完整键盘支持）
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
        self.screen_width = 1920
        self.screen_height = 1080
        self.display_scale = 1.0

        # 修饰键状态
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.alt_pressed = False

    def log(self, msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def connect(self):
        """连接服务器"""
        try:
            self.sock = socket.socket()
            self.sock.settimeout(5)
            self.log(f"连接 {self.ip}:{self.port}...")
            self.sock.connect((self.ip, self.port))

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

    def draw_mouse_on_image(self, image):
        """在图像上绘制鼠标位置"""
        if not self.streaming:
            return image

        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        draw = ImageDraw.Draw(image)

        img_width, img_height = image.size
        mouse_img_x = int(self.remote_mouse_x * img_width / self.screen_width)
        mouse_img_y = int(self.remote_mouse_y * img_height / self.screen_height)

        mouse_img_x = max(0, min(mouse_img_x, img_width - 1))
        mouse_img_y = max(0, min(mouse_img_y, img_height - 1))

        size = max(8, min(20, img_width // 50))

        draw.ellipse([(mouse_img_x - size, mouse_img_y - size),
                      (mouse_img_x + size, mouse_img_y + size)],
                     outline='white', width=2)
        draw.ellipse([(mouse_img_x - size // 2, mouse_img_y - size // 2),
                      (mouse_img_x + size // 2, mouse_img_y + size // 2)],
                     fill='red', outline='white', width=1)
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

                len_data = b''
                while len(len_data) < 4:
                    chunk = self.sock.recv(4 - len(len_data))
                    if not chunk:
                        return
                    len_data += chunk

                img_len = struct.unpack('>I', len_data)[0]

                if img_len > 0 and img_len < 10 * 1024 * 1024:
                    img_data = b''
                    while len(img_data) < img_len:
                        chunk = self.sock.recv(min(8192, img_len - len(img_data)))
                        if not chunk:
                            break
                        img_data += chunk

                    if len(img_data) == img_len:
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
        """更新显示"""
        if not self.streaming or not self.root:
            return

        try:
            try:
                img_data = self.image_queue.get_nowait()
            except queue.Empty:
                self.root.after(33, self.update_display)
                return

            image = Image.open(io.BytesIO(img_data))
            image = self.draw_mouse_on_image(image)

            width = self.root.winfo_width()
            height = self.root.winfo_height()

            if width > 10 and height > 10:
                img_width, img_height = image.size
                scale_w = width / img_width
                scale_h = height / img_height
                self.display_scale = min(scale_w, scale_h)

                new_width = int(img_width * self.display_scale)
                new_height = int(img_height * self.display_scale)

                if self.display_scale != 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            self.current_photo = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_photo)

            if hasattr(self, 'info_label') and self.info_label:
                self.info_label.destroy()
                self.info_label = None

            self.frame_count += 1
            if time.time() - self.last_time >= 1.0:
                fps = self.frame_count
                self.root.title(f"Teto 远程控制 - {fps} FPS")
                self.frame_count = 0
                self.last_time = time.time()

        except Exception as e:
            self.log(f"显示错误: {e}")

        self.root.after(33, self.update_display)

    def send_command(self, cmd):
        """发送命令"""
        try:
            if self.sock:
                self.sock.send(cmd.encode())
        except:
            pass

    def send_key_event(self, key, is_press=True):
        """发送键盘事件"""
        event_type = "KEY_DOWN" if is_press else "KEY_UP"
        self.send_command(f"{event_TYPE}:{key}")

    def on_mouse_move(self, event):
        """鼠标移动"""
        if self.video_label and self.current_photo:
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            img_w = self.current_photo.width()
            img_h = self.current_photo.height()

            if label_w > 0 and img_w > 0:
                offset_x = (label_w - img_w) // 2
                offset_y = (label_h - img_h) // 2

                rel_x = event.x - offset_x
                rel_y = event.y - offset_y

                if 0 <= rel_x < img_w and 0 <= rel_y < img_h:
                    remote_x = int(rel_x * self.screen_width / img_w)
                    remote_y = int(rel_y * self.screen_height / img_h)

                    remote_x = max(0, min(remote_x, self.screen_width))
                    remote_y = max(0, min(remote_y, self.screen_height))

                    self.remote_mouse_x = remote_x
                    self.remote_mouse_y = remote_y

                    self.send_command(f"MOVE:{remote_x}:{remote_y}")

    def on_click(self, event):
        """左键点击"""
        self.send_command("CLICK_LEFT")

    def on_right_click(self, event):
        """右键点击"""
        self.send_command("CLICK_RIGHT")

    def on_key_press(self, event):
        """键盘按下 - 完整支持"""
        # 获取按键字符或名称
        key = event.keysym

        # 处理修饰键
        if key == 'Shift_L' or key == 'Shift_R':
            self.shift_pressed = True
            self.send_command(f"KEY_DOWN:shift")
            return
        elif key == 'Control_L' or key == 'Control_R':
            self.ctrl_pressed = True
            self.send_command(f"KEY_DOWN:ctrl")
            return
        elif key == 'Alt_L' or key == 'Alt_R':
            self.alt_pressed = True
            self.send_command(f"KEY_DOWN:alt")
            return

        # 获取实际字符（考虑Shift）
        char = event.char
        if char and char != '':
            # 有字符输入（字母、数字、标点符号）
            self.send_command(f"KEY_DOWN:{char}")
            self.send_command(f"KEY_UP:{char}")
        else:
            # 特殊键
            special_keys = {
                'Return': 'enter',
                'BackSpace': 'backspace',
                'Tab': 'tab',
                'Escape': 'esc',
                'space': 'space',
                'Delete': 'delete',
                'Insert': 'insert',
                'Home': 'home',
                'End': 'end',
                'Page_Up': 'page_up',
                'Page_Down': 'page_down',
                'Up': 'up',
                'Down': 'down',
                'Left': 'left',
                'Right': 'right',
                'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4',
                'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8',
                'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12'
            }

            if key in special_keys:
                special_key = special_keys[key]
                self.send_command(f"KEY_DOWN:{special_key}")
                self.send_command(f"KEY_UP:{special_key}")

        # 调试输出
        if char:
            self.log(f"按键: {char} (键名: {key})")
        else:
            self.log(f"特殊键: {key}")

    def on_key_release(self, event):
        """键盘释放"""
        key = event.keysym

        # 处理修饰键释放
        if key == 'Shift_L' or key == 'Shift_R':
            self.shift_pressed = False
            self.send_command(f"KEY_UP:shift")
        elif key == 'Control_L' or key == 'Control_R':
            self.ctrl_pressed = False
            self.send_command(f"KEY_UP:ctrl")
        elif key == 'Alt_L' or key == 'Alt_R':
            self.alt_pressed = False
            self.send_command(f"KEY_UP:alt")

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

        # 绑定键盘事件
        self.root.bind_all("<KeyPress>", self.on_key_press)
        self.root.bind_all("<KeyRelease>", self.on_key_release)

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
                                   text="等待视频流...\n\n移动鼠标控制远程指针\n点击鼠标进行远程点击\n支持键盘输入和标点符号",
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