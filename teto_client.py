#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（修复显示问题）
使用线程安全的方式更新GUI
"""
import sys
import socket
import tkinter as tk
import threading
import struct
from PIL import Image, ImageTk
import io
import time
import queue

TETO_PROTOCOL = b"teto_run"


class RemoteClient:
    def __init__(self, ip, room_id, port=5000):
        self.ip = ip
        self.room = str(room_id).strip()
        self.port = port
        self.control_sock = None
        self.screen_sock = None
        self.root = None
        self.last_x = None
        self.last_y = None
        self.streaming = False
        self.video_label = None
        self.canvas = None
        self.current_image = None
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.receive_thread = None
        self.image_queue = queue.Queue(maxsize=2)  # 图像队列，只保留最新2帧
        self.running = True

    def log(self, msg):
        """调试输出"""
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def connect(self):
        """连接控制端口"""
        try:
            self.control_sock = socket.socket()
            self.control_sock.settimeout(10)
            self.log(f"正在连接到 {self.ip}:{self.port}...")
            self.control_sock.connect((self.ip, self.port))

            self.control_sock.send(TETO_PROTOCOL)
            self.control_sock.send(f"ROOM:{self.room}".encode())

            res = self.control_sock.recv(1024).decode()
            self.log(f"控制连接响应: {res}")

            if res != "OK":
                self.log("❌ 连接失败")
                return False

            self.log("✓ 控制连接成功！")
            return True

        except Exception as e:
            self.log(f"❌ 控制连接失败: {e}")
            return False

    def start_video_stream(self):
        """请求开始视频流传输"""
        try:
            # 连接屏幕传输端口
            self.log(f"正在连接屏幕端口 {self.ip}:{self.port + 1}...")
            self.screen_sock = socket.socket()
            self.screen_sock.settimeout(5)
            self.screen_sock.connect((self.ip, self.port + 1))

            self.screen_sock.send(TETO_PROTOCOL)
            self.screen_sock.send(f"ROOM:{self.room}".encode())

            res = self.screen_sock.recv(1024).decode()
            self.log(f"屏幕连接响应: {res}")

            if res != "OK":
                self.log("❌ 屏幕传输连接失败")
                return False

            self.log("✓ 屏幕连接成功！")

            # 通知控制端口开始传输
            self.control_sock.send(b"START_STREAM:")
            response = self.control_sock.recv(1024).decode()
            self.log(f"启动流响应: {response}")

            if response == "STREAM_OK":
                self.streaming = True
                self.log("✓ 视频流已启动")
                return True
            else:
                self.log(f"❌ 启动视频流失败: {response}")
                return False

        except Exception as e:
            self.log(f"❌ 启动视频流异常: {e}")
            return False

    def receive_video_stream(self):
        """接收视频流数据（在单独线程中运行）"""
        self.log("开始接收视频流...")
        frame_count = 0

        while self.streaming and self.screen_sock and self.running:
            try:
                self.screen_sock.settimeout(1.0)

                # 接收4字节的图像长度
                len_data = b''
                while len(len_data) < 4:
                    chunk = self.screen_sock.recv(4 - len(len_data))
                    if not chunk:
                        self.log("连接已断开")
                        return
                    len_data += chunk

                img_len = struct.unpack('>I', len_data)[0]

                if img_len > 0 and img_len < 1024 * 1024 * 10:
                    # 接收图像数据
                    img_data = b''
                    while len(img_data) < img_len:
                        chunk = self.screen_sock.recv(min(8192, img_len - len(img_data)))
                        if not chunk:
                            break
                        img_data += chunk

                    if len(img_data) == img_len:
                        frame_count += 1

                        # 清空队列，只保留最新帧
                        while not self.image_queue.empty():
                            try:
                                self.image_queue.get_nowait()
                            except queue.Empty:
                                break

                        # 将图像数据放入队列
                        self.image_queue.put(img_data)

                        # 每30帧打印一次统计
                        if frame_count % 30 == 0:
                            self.log(f"已接收 {frame_count} 帧")

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"接收视频流错误: {e}")
                break

        self.log(f"视频流接收结束，共接收 {frame_count} 帧")

    def update_image(self):
        """在GUI线程中更新图像"""
        if not self.running or not self.root:
            return

        try:
            # 从队列中获取最新图像（非阻塞）
            try:
                img_data = self.image_queue.get_nowait()
            except queue.Empty:
                # 没有新图像，稍后再试
                if self.root:
                    self.root.after(33, self.update_image)  # 约30fps
                return

            # 解码图像
            image = Image.open(io.BytesIO(img_data))

            # 获取窗口大小
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()

            # 缩放图像以适应窗口
            if window_width > 100 and window_height > 100:
                img_width, img_height = image.size
                scale = min(window_width / img_width, window_height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)

                if scale != 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 转换为Tkinter格式
            self.current_image = ImageTk.PhotoImage(image)

            # 更新显示
            if self.video_label:
                self.video_label.config(image=self.current_image)

                # 隐藏提示信息
                if hasattr(self, 'info_label') and self.info_label:
                    self.info_label.destroy()
                    self.info_label = None

            # 更新帧率显示
            self.frame_count += 1
            current_time = time.time()
            if current_time - self.last_fps_time >= 1.0:
                fps = self.frame_count / (current_time - self.last_fps_time)
                if self.root:
                    self.root.title(f"Teto 远程控制 - {fps:.1f} FPS")
                self.frame_count = 0
                self.last_fps_time = current_time

        except Exception as e:
            self.log(f"更新图像错误: {e}")

        # 继续下一帧
        if self.root and self.running:
            self.root.after(33, self.update_image)  # 约30fps

    def on_mouse(self, e):
        """鼠标移动事件"""
        if self.last_x is not None:
            dx = e.x - self.last_x
            dy = e.y - self.last_y
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
            threading.Timer(0.05, lambda: self.send_click_release()).start()
        except:
            pass

    def send_click_release(self):
        """发送鼠标释放事件"""
        try:
            self.control_sock.send(b"CLICK:0")
        except:
            pass

    def on_closing(self):
        """关闭窗口时的清理工作"""
        self.log("正在关闭客户端...")
        self.running = False
        self.streaming = False

        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)

        try:
            if self.control_sock:
                self.control_sock.send(b"STOP_STREAM:")
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
        self.root.title("Teto 远程控制")
        self.root.geometry("1024x768")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 创建主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建显示视频的标签
        self.video_label = tk.Label(main_frame, bg="#2b2b2b")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        # 创建透明画布覆盖在视频上用于接收鼠标事件
        self.canvas = tk.Canvas(main_frame, bg="black", cursor="cross", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.canvas.bind("<Motion>", self.on_mouse)
        self.canvas.bind("<Button-1>", self.on_click)

        # 添加状态栏
        self.status_bar = tk.Label(self.root, text="已连接 - 等待视频流...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 显示提示信息
        self.info_label = tk.Label(main_frame,
                                   text="正在等待视频流...\n\n移动鼠标控制远程指针\n点击鼠标进行远程点击",
                                   font=("Arial", 14),
                                   fg="white",
                                   bg="#2b2b2b",
                                   justify=tk.CENTER)
        self.info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # 启动视频接收线程
        self.receive_thread = threading.Thread(target=self.receive_video_stream, daemon=True)
        self.receive_thread.start()

        # 启动图像更新循环（在GUI线程中）
        self.root.after(100, self.update_image)

        # 更新状态栏
        self.update_status()

        self.log("GUI已启动")
        self.root.mainloop()

    def update_status(self):
        """更新状态栏"""
        if self.frame_count > 0:
            self.status_bar.config(text=f"已连接 - 房间 {self.room} - 视频传输中 ({self.frame_count} fps)")
        elif self.streaming:
            self.status_bar.config(text=f"已连接 - 房间 {self.room} - 等待视频数据...")
        else:
            self.status_bar.config(text=f"已连接 - 房间 {self.room} - 控制模式")

        if self.root:
            self.root.after(1000, self.update_status)

    def run(self):
        """运行客户端"""
        if not self.connect():
            print("连接失败，请检查IP、房间号和网络")
            input("按回车键退出...")
            return

        if not self.start_video_stream():
            print("视频流启动失败，但鼠标控制功能可用")

        self.start_gui()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("=" * 50)
        print("Teto 远程客户端")
        print("=" * 50)
        print("用法: python teto_client.py IP 房间号 [端口]")
        print("\n示例:")
        print("  python teto_client.py 192.168.1.100 123456 5000")
        print("  python teto_client.py 127.0.0.1 123456 5000")
        print("=" * 50)
        sys.exit(1)

    ip = sys.argv[1]
    room = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000

    print(f"\n尝试连接:")
    print(f"  服务器: {ip}:{port}")
    print(f"  房间号: {room}")
    print(f"  屏幕端口: {port + 1}\n")

    client = RemoteClient(ip, room, port)
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n客户端已退出")
    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
        input("\n按回车键退出...")