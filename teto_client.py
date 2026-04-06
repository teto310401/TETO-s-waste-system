#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（控制端）
修复房间号发送问题
"""
import sys
import socket
import tkinter as tk
import threading
import struct
from PIL import Image, ImageTk
import io
import time

TETO_PROTOCOL = b"teto_run"


class RemoteClient:
    def __init__(self, ip, room_id, port=5000):
        self.ip = ip
        self.room = str(room_id).strip()  # 确保是字符串并去除空格
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

    def connect(self):
        """连接控制端口"""
        try:
            self.control_sock = socket.socket()
            self.control_sock.settimeout(10)
            print(f"正在连接到 {self.ip}:{self.port}...")
            self.control_sock.connect((self.ip, self.port))

            # 发送协议标识
            self.control_sock.send(TETO_PROTOCOL)
            print(f"已发送协议: {TETO_PROTOCOL}")

            # 发送房间号（确保格式正确）
            room_msg = f"ROOM:{self.room}".encode()
            self.control_sock.send(room_msg)
            print(f"已发送房间号: {room_msg}")

            # 接收响应
            res = self.control_sock.recv(1024).decode()
            print(f"收到响应: {res}")

            if res != "OK":
                print(f"❌ 连接失败: 房间号错误或服务器拒绝")
                print(f"   您的房间号: {self.room}")
                print(f"   请检查服务端显示的房间号是否正确")
                return False

            print("✓ 控制连接成功！")
            return True

        except socket.timeout:
            print("❌ 连接超时，请检查网络和防火墙设置")
            return False
        except ConnectionRefusedError:
            print("❌ 连接被拒绝，请确认服务端已启动且端口正确")
            return False
        except Exception as e:
            print(f"❌ 控制连接失败: {e}")
            return False

    def start_video_stream(self):
        """请求开始视频流传输"""
        try:
            # 连接屏幕传输端口
            print(f"正在连接屏幕端口 {self.ip}:{self.port + 1}...")
            self.screen_sock = socket.socket()
            self.screen_sock.settimeout(5)
            self.screen_sock.connect((self.ip, self.port + 1))

            # 发送协议和房间号
            self.screen_sock.send(TETO_PROTOCOL)
            self.screen_sock.send(f"ROOM:{self.room}".encode())

            res = self.screen_sock.recv(1024).decode()
            if res != "OK":
                print(f"❌ 屏幕传输连接失败: {res}")
                return False

            print("✓ 屏幕连接成功！")

            # 通知控制端口开始传输
            self.control_sock.send(b"START_STREAM:")
            response = self.control_sock.recv(1024).decode()
            print(f"启动流响应: {response}")

            if response == "STREAM_OK":
                self.streaming = True
                print("✓ 视频流已启动，目标帧率: 30 FPS")
                return True
            else:
                print(f"❌ 启动视频流失败: {response}")
                return False

        except Exception as e:
            print(f"❌ 启动视频流异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop_video_stream(self):
        """停止视频流传输"""
        try:
            self.streaming = False
            if self.control_sock:
                self.control_sock.send(b"STOP_STREAM:")
                try:
                    self.control_sock.recv(1024)
                except:
                    pass
            if self.screen_sock:
                self.screen_sock.close()
        except:
            pass
        print("视频流已停止")

    def receive_video_stream(self):
        """接收视频流数据"""
        print("开始接收视频流...")

        while self.streaming and self.screen_sock:
            try:
                self.screen_sock.settimeout(1.0)

                # 接收4字节的图像长度
                len_data = b''
                while len(len_data) < 4:
                    chunk = self.screen_sock.recv(4 - len(len_data))
                    if not chunk:
                        raise Exception("连接已断开")
                    len_data += chunk

                img_len = struct.unpack('>I', len_data)[0]

                if 0 < img_len < 1024 * 1024 * 10:  # 10MB限制
                    # 接收图像数据
                    img_data = b''
                    while len(img_data) < img_len:
                        chunk = self.screen_sock.recv(min(8192, img_len - len(img_data)))
                        if not chunk:
                            break
                        img_data += chunk

                    if len(img_data) == img_len:
                        self.display_image(img_data)

                        # 统计帧率
                        self.frame_count += 1
                        current_time = time.time()
                        if current_time - self.last_fps_time >= 1.0:
                            fps = self.frame_count / (current_time - self.last_fps_time)
                            if self.root:
                                self.root.title(f"Teto 远程控制 - {fps:.1f} FPS")
                            print(f"帧率: {fps:.1f} FPS, 已接收 {self.frame_count} 帧")
                            self.frame_count = 0
                            self.last_fps_time = current_time
                    else:
                        print(f"接收不完整: {len(img_data)}/{img_len}")
                else:
                    print(f"无效长度: {img_len}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收视频流错误: {e}")
                break

        print("视频流接收结束")

    def display_image(self, img_data):
        """显示图像"""
        if not self.root or not self.video_label:
            return

        try:
            image = Image.open(io.BytesIO(img_data))

            self.root.update_idletasks()
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()

            if window_width > 100 and window_height > 100:
                img_width, img_height = image.size
                scale = min(window_width / img_width, window_height / img_height)
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)

                if scale != 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            self.current_image = ImageTk.PhotoImage(image)
            self.video_label.config(image=self.current_image)

            if hasattr(self, 'info_label') and self.info_label:
                self.info_label.destroy()
                self.info_label = None

        except Exception as e:
            print(f"显示图像错误: {e}")

    def on_mouse(self, e):
        """鼠标移动"""
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
        """鼠标点击"""
        try:
            self.control_sock.send(b"CLICK:1")
            threading.Timer(0.05, lambda: self.send_click_release()).start()
        except:
            pass

    def send_click_release(self):
        """释放鼠标"""
        try:
            self.control_sock.send(b"CLICK:0")
        except:
            pass

    def on_closing(self):
        """关闭窗口"""
        print("正在关闭客户端...")
        self.streaming = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)
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
        """启动GUI"""
        self.root = tk.Tk()
        self.root.title("Teto 远程控制")
        self.root.geometry("1024x768")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.video_label = tk.Label(main_frame, bg="#2b2b2b")
        self.video_label.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_frame, bg="black", cursor="cross", highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.canvas.bind("<Motion>", self.on_mouse)
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_bar = tk.Label(self.root, text="正在连接...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.info_label = tk.Label(main_frame,
                                   text=f"正在连接房间 {self.room}...\n\n如果长时间无响应，请检查：\n1. 服务端是否运行\n2. 房间号是否正确\n3. 防火墙是否开放端口",
                                   font=("Arial", 12),
                                   fg="white",
                                   bg="#2b2b2b",
                                   justify=tk.CENTER)
        self.info_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self.receive_thread = threading.Thread(target=self.receive_video_stream, daemon=True)
        self.receive_thread.start()

        self.update_status()
        self.root.mainloop()

    def update_status(self):
        """更新状态栏"""
        if self.streaming:
            self.status_bar.config(text=f"已连接 - 房间 {self.room} - 实时画面传输中")
        elif self.control_sock:
            self.status_bar.config(text=f"已连接 - 房间 {self.room} - 等待视频流...")
        else:
            self.status_bar.config(text=f"连接失败 - 房间 {self.room}")

        if self.root:
            self.root.after(1000, self.update_status)

    def run(self):
        """运行"""
        if not self.connect():
            print("\n连接失败！请确认：")
            print(f"  1. 服务端已启动")
            print(f"  2. 房间号 '{self.room}' 正确")
            print(f"  3. IP地址 {self.ip}:{self.port} 可访问")
            print(f"  4. 防火墙已开放端口 {self.port} 和 {self.port + 1}")
            input("\n按回车键退出...")
            return

        if not self.start_video_stream():
            print("\n警告: 视频流启动失败，但鼠标控制功能可用")

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
        print("\n注意: 房间号必须与服务端显示的一致")
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