#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端（被控制端）
增加30帧实时屏幕传输功能
"""
import sys
import socket
import threading
import struct
import time
import ctypes
import platform
import os
import zlib
from PIL import ImageGrab, Image
import io

TETO_PROTOCOL = b"teto_run"


class RemoteServer:
    def __init__(self, port=5000):
        self.port = port
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True
        self.local_mouse_time = 0
        self.screen_streaming = False  # 屏幕传输开关
        self.screen_socket = None  # 屏幕传输专用socket

    def _check_mouse(self):
        if platform.system() != "Windows":
            return True
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self.local_mouse_time = time.time()
        except:
            pass

    def _capture_screen(self):
        """截取屏幕并返回压缩后的JPEG数据"""
        try:
            # 截取整个屏幕
            screenshot = ImageGrab.grab()

            # 压缩图片质量（70%质量，平衡带宽和清晰度）
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format='JPEG', quality=70, optimize=True)
            img_data = img_buffer.getvalue()

            # 使用zlib进一步压缩（可选）
            # compressed = zlib.compress(img_data, level=6)

            return img_data
        except Exception as e:
            print(f"截图失败: {e}")
            return None

    def _send_screen_frame(self, sock):
        """发送单帧屏幕数据"""
        img_data = self._capture_screen()
        if img_data is None:
            return False

        try:
            # 发送数据长度（4字节）+ 图片数据
            sock.send(struct.pack('>I', len(img_data)))
            sock.send(img_data)
            return True
        except Exception as e:
            print(f"发送屏幕帧失败: {e}")
            return False

    def _screen_stream_thread(self, sock):
        """屏幕传输线程，保持30帧速率"""
        print("屏幕传输线程启动，目标帧率: 30 FPS")
        frame_interval = 1.0 / 30.0  # 33.33ms每帧

        while self.screen_streaming and self.running:
            start_time = time.time()

            # 发送一帧
            if not self._send_screen_frame(sock):
                break

            # 控制帧率
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

        print("屏幕传输线程结束")

    def handle_control_client(self, sock):
        """处理控制连接（鼠标控制）"""
        print("控制客户端已连接")
        try:
            while self.running:
                data = sock.recv(1024).decode()
                if not data:
                    break

                if data.startswith("MOVE:"):
                    if time.time() - self.local_mouse_time > 2:
                        dx, dy = map(int, data[5:].split(","))
                        ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
                elif data.startswith("CLICK:"):
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                elif data.startswith("START_STREAM:"):
                    # 客户端请求开始屏幕传输
                    if not self.screen_streaming:
                        self.screen_streaming = True
                        # 创建新的socket用于屏幕传输
                        self.screen_socket = socket.socket()
                        self.screen_socket.connect((sock.getpeername()[0], self.port + 1))
                        sock.send(b"STREAM_OK")
                        # 启动屏幕传输线程
                        stream_thread = threading.Thread(
                            target=self._screen_stream_thread,
                            args=(self.screen_socket,),
                            daemon=True
                        )
                        stream_thread.start()
                    else:
                        sock.send(b"STREAM_ALREADY")
                elif data.startswith("STOP_STREAM:"):
                    self.screen_streaming = False
                    if self.screen_socket:
                        try:
                            self.screen_socket.close()
                        except:
                            pass
                        self.screen_socket = None
                    sock.send(b"STREAM_STOPPED")
        except Exception as e:
            print(f"控制连接异常: {e}")
        print("控制连接断开")

    def handle_screen_client(self, sock):
        """处理屏幕传输连接（纯数据发送）"""
        print("屏幕传输客户端已连接")
        try:
            # 等待控制线程设置标志
            while self.running:
                if self.screen_streaming:
                    self._screen_stream_thread(sock)
                else:
                    time.sleep(0.1)
        except Exception as e:
            print(f"屏幕传输连接异常: {e}")
        print("屏幕传输连接断开")

    def start(self):
        print(f"===== 远程服务端启动 =====")
        print(f"房间号: {self.room_id}")
        print(f"控制端口: {self.port}")
        print(f"屏幕端口: {self.port + 1}")
        print(f"协议: TETO_RUN")
        print("=========================\n")

        # 控制端口监听
        control_socket = socket.socket()
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(("0.0.0.0", self.port))
        control_socket.listen(5)

        # 屏幕传输端口监听
        screen_socket = socket.socket()
        screen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        screen_socket.bind(("0.0.0.0", self.port + 1))
        screen_socket.listen(5)

        # 启动屏幕连接接受线程
        def accept_screen():
            while self.running:
                try:
                    conn, addr = screen_socket.accept()
                    # 验证协议
                    proto = conn.recv(len(TETO_PROTOCOL))
                    if proto != TETO_PROTOCOL:
                        conn.close()
                        continue
                    room = conn.recv(1024).decode().replace("ROOM:", "")
                    if room == self.room_id:
                        conn.send(b"OK")
                        threading.Thread(target=self.handle_screen_client, args=(conn,), daemon=True).start()
                    else:
                        conn.send(b"ERROR")
                        conn.close()
                except:
                    break

        screen_thread = threading.Thread(target=accept_screen, daemon=True)
        screen_thread.start()

        while self.running:
            try:
                conn, addr = control_socket.accept()
                proto = conn.recv(len(TETO_PROTOCOL))
                if proto != TETO_PROTOCOL:
                    conn.close()
                    continue
                room = conn.recv(1024).decode().replace("ROOM:", "")
                if room == self.room_id:
                    conn.send(b"OK")
                    threading.Thread(target=self.handle_control_client, args=(conn,), daemon=True).start()
                else:
                    conn.send(b"ERROR")
                    conn.close()
            except:
                break

        control_socket.close()
        screen_socket.close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    server = RemoteServer(port)
    try:
        server.start()
    except KeyboardInterrupt:
        server.running = False
        print("\n服务端已停止")