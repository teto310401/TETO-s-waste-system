#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（控制端）
增加实时视频接收和显示功能
"""
import sys
import socket
import tkinter as tk
import threading
import struct
from PIL import Image, ImageTk
import io

TETO_PROTOCOL = b"teto_run"


class RemoteClient:
    def __init__(self, ip, room_id, port=5000):
        self.ip = ip
        self.room = room_id
        self.port = port
        self.control_sock = None  # 控制连接
        self.screen_sock = None  # 屏幕传输连接
        self.root = None
        self.last_x = None
        self.last_y = None
        self.streaming = False  # 是否正在接收视频流
        self.video_label = None  # 用于显示视频的标签
        self.canvas = None  # 画布（用于鼠标控制）
        self.current_image = None  # 当前显示的图片对象
        self.frame_count = 0  # 统计帧数
        self.last_fps_time = time.time()

    def connect(self):
        """连接控制端口"""
        self.control_sock = socket.socket()
        self.control_sock.settimeout(10)
        self.control_sock.connect((self.ip, self.port))
        self.control_sock.send(TETO_PROTOCOL)
        self.control_sock.send(f"ROOM:{self.room}".encode())
        res = self.control_sock.recv(1024).decode()
        if res != "OK":
            print("房间号错误或连接失败")
            return False

        # 连接成功后请求开始视频流
        self.start_video_stream()

        print("连接成功！")
        return True

    def start_video_stream(self):
        """请求开始视频流传输"""
        try:
            # 连接屏幕传输端口
            self.screen_sock = socket.socket()
            self.screen_sock.settimeout(5)
            self.screen_sock.connect((self.ip, self.port + 1))
            self.screen_sock.send(TETO_PROTOCOL)
            self.screen_sock.send(f"ROOM:{self.room}".encode())
            res = self.screen_sock.recv(1024).decode()
            if res != "OK":
                print("屏幕传输连接失败")
                return False

            # 通知控制端口开始传输
            self.control_sock.send(b"START_STREAM:")
            response = self.control_sock.recv(1024).decode()
            if response == "STREAM_OK":
                self.streaming = True
                print("视频流已启动，目标帧率: 30 FPS")
                # 启动接收线程
                receive_thread = threading.Thread(target=self.receive_video_stream, daemon=True)
                receive_thread.start()
                return True
            else:
                print(f"启动视频流失败: {response}")
                return False
        except Exception as e:
            print(f"启动视频流异常: {e}")
            return False

    def stop_video_stream(self):
        """停止视频流传输"""
        try:
            self.streaming = False
            if self.control_sock:
                self.control_sock.send(b"STOP_STREAM:")
                self.control_sock.recv(1024)
            if self.screen_sock:
                self.screen_sock.close()
        except:
            pass
        print("视频流已停止")

    def receive_video_stream(self):
        """接收视频流数据"""
        print("开始接收视频流...")

        while self.streaming and self.control_sock:
            try:
                # 接收4字节的图像长度
                len_data = self.screen_sock.recv(4)
                if not len_data:
                    break

                img_len = struct.unpack('>I', len_data)[0]

                # 接收图像数据
                img_data = b''
                while len(img_data) < img_len:
                    chunk = self.screen_sock.recv(min(8192, img_len - len(img_data)))
                    if not chunk:
                        break
                    img_data += chunk

                if len(img_data) == img_len:
                    # 解码并显示图像
                    self.display_image(img_data)

                    # 统计帧率
                    self.frame_count += 1
                    current_time = time.time()
                    if current_time - self.last_fps_time >= 1.0:
                        fps = self.frame_count / (current_time - self.last_fps_time)
                        if self.root:
                            self.root.title(f"Teto 远程控制 - {fps:.1f} FPS")
                        self.frame_count = 0
                        self.last_fps_time = current_time

            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收视频流错误: {e}")
                break

        print("视频流接收结束")

    def display_image(self, img_data):
        """在GUI中显示接收到的图像"""
        if not self.root or not self.video_label:
            return

        try:
            # 将JPEG数据转换为PIL Image
            image = Image.open(io.BytesIO(img_data))

            # 调整图像大小以适应窗口（保持宽高比）
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()

            if window_width > 10 and window_height > 10:
                # 计算缩放比例
                img_width, img_height = image.size
                scale = min(window_width / img_width, window_height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)

                # 缩放图像
                if scale < 0.95 or scale > 1.05:  # 只在需要时缩放
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 转换为Tkinter可用的格式
            self.current_image = ImageTk.PhotoImage(image)

            # 更新显示
            self.video_label.config(image=self.current_image)

            # 更新画布大小以匹配图像
            if self.canvas:
                self.canvas.config(width=image.width, height=image.height)

        except Exception as e:
            print(f"显示图像错误: {e}")

    def on_mouse(self, e):
        """鼠标移动事件 - 发送相对移动坐标"""
        if self.last_x is not None:
            dx = e.x - self.last_x
            dy = e.y - self.last_y
            # 限制移动范围，避免过快
            dx = max(-100, min(100, dx))
            dy = max(-100, min(100, dy))
            if dx != 0 or dy != 0:
                try:
                    self.control_sock.send(f"MOVE:{dx},{dy}".encode())
                except:
                    pass
        self.last_x = e.x
        self.last_y = e.y

    def on_click(self, e):
        """鼠标点击事件"""
        try:
            self.control_sock.send(b"CLICK:1")
            # 简单模拟点击释放
            threading.Timer(0.05, lambda: self.send_click_release()).start()
        except:
            pass

    def send_click_release(self):
        """发送鼠标释放事件"""
        try:
            self.control_sock.send(b"CLICK:0")
        except:
            pass

    def on_window_resize(self, e):
        """窗口大小改变时重新调整图像"""
        if self.current_image:
            # 重新显示当前图像以适应新窗口大小
            self.display_image_from_current()

    def display_image_from_current(self):
        """重新显示当前图像（用于窗口调整）"""
        # 这个方法可以优化，目前简单处理
        pass

    def on_closing(self):
        """关闭窗口时的清理工作"""
        print("正在关闭客户端...")
        self.streaming = False
        try:
            if self.control_sock:
                self.stop_video_stream()
                self.control_sock.close()
            if self.screen_sock:
                self.screen_sock.close()
        except:
            pass
        if self.root:
            self.root.destroy()

    def start_gui(self):
        """启动GUI界面"""
        self.root = tk.Tk()
        self.root.title("Teto 远程控制 - 连接中...")
        self.root.geometry("1024x768")

        # 设置关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 创建主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建显示视频的标签（背景设为灰色）
        self.video_label = tk.Label(main_frame, bg="#2b2b2b")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 创建透明画布覆盖在视频上用于接收鼠标事件
        self.canvas = tk.Canvas(main_frame, bg="black", cursor="cross", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.canvas.bind("<Motion>", self.on_mouse)
        self.canvas.bind("<Button-1>", self.on_click)

        # 添加状态栏
        status_bar = tk.Label(self.root, text="已连接 - 实时画面传输中", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 绑定窗口大小改变事件
        self.root.bind("<Configure>", self.on_window_resize)

        # 显示提示信息
        info_label = tk.Label(main_frame,
                              text="正在等待视频流...\n\n移动鼠标控制远程指针\n点击鼠标进行远程点击",
                              font=("Arial", 12),
                              fg="white",
                              bg="#2b2b2b")
        info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 3秒后移除提示
        self.root.after(3000, info_label.destroy)

        # 启动GUI主循环
        self.root.mainloop()

    def run(self):
        """运行客户端"""
        if not self.connect():
            print("连接失败，请检查IP、房间号和网络")
            return
        self.start_gui()


if __name__ == "__main__":
    import time

    if len(sys.argv) < 3:
        print("用法: python teto_client.py IP 房间号 [端口]")
        print("示例: python teto_client.py 192.168.1.100 123456 5000")
        sys.exit(1)

    ip = sys.argv[1]
    room = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000

    client = RemoteClient(ip, room, port)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n客户端已退出")
    except Exception as e:
        print(f"错误: {e}")