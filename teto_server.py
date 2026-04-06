#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端
"""
import socket
import threading
import struct
import time
import cv2
import numpy as np
from PIL import ImageGrab
import pyautogui
import sys

LISTEN_PORT = 5000
FPS = 30
JPEG_QUALITY = 60
pyautogui.FAILSAFE = False


class RemoteServer:
    def __init__(self, port=5000):
        self.port = port
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True

    def send_screen(self, conn):
        """发送屏幕画面"""
        print("📹 屏幕传输线程启动")
        frame_count = 0
        last_time = time.time()

        try:
            while self.running:
                # 截图
                img = ImageGrab.grab()

                # 转换为OpenCV格式并压缩
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

                if not ret:
                    continue

                # 发送数据长度和图片数据
                data = jpg.tobytes()
                conn.sendall(struct.pack('>I', len(data)))
                conn.sendall(data)

                # 统计帧率
                frame_count += 1
                if time.time() - last_time >= 1.0:
                    fps = frame_count / (time.time() - last_time)
                    print(f"帧率: {fps:.1f} FPS")
                    frame_count = 0
                    last_time = time.time()

                time.sleep(1 / FPS)

        except Exception as e:
            print(f"屏幕传输错误: {e}")
        finally:
            conn.close()
            print("屏幕传输线程结束")

    def handle_control(self, conn):
        """处理控制命令"""
        print("🎮 控制线程启动")

        try:
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break

                cmd = data.decode('utf-8', 'ignore')

                if cmd.startswith("MOVE:"):
                    try:
                        _, x, y = cmd.split(":")
                        pyautogui.moveTo(int(float(x)), int(float(y)))
                    except:
                        pass

                elif cmd == "CLICK_LEFT":
                    pyautogui.click()

                elif cmd == "CLICK_RIGHT":
                    pyautogui.rightClick()

                elif cmd.startswith("KEY:"):
                    key = cmd.replace("KEY:", "")
                    pyautogui.press(key)

                elif cmd == "GET_SCREEN_SIZE":
                    screen = pyautogui.size()
                    conn.sendall(f"{screen.width}:{screen.height}".encode())

        except Exception as e:
            print(f"控制错误: {e}")
        finally:
            conn.close()
            print("控制线程结束")

    def start(self):
        """启动服务端"""
        print("=" * 50)
        print("Teto 远程服务端")
        print("=" * 50)
        print(f"房间号: {self.room_id}")
        print(f"端口: {self.port}")
        print(f"帧率: {FPS} FPS")
        print("=" * 50)
        print("等待连接...\n")

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.port))
        server.listen(5)

        try:
            while self.running:
                conn, addr = server.accept()
                print(f"客户端已连接: {addr}")

                # 验证房间号
                try:
                    room = conn.recv(1024).decode().strip()
                    if room == self.room_id:
                        conn.send(b"OK")
                        print("房间号验证通过")

                        # 启动线程
                        threading.Thread(target=self.send_screen, args=(conn,), daemon=True).start()
                        threading.Thread(target=self.handle_control, args=(conn,), daemon=True).start()
                    else:
                        conn.send(b"ERROR")
                        conn.close()
                        print(f"房间号错误: {room}")
                except:
                    conn.close()

        except KeyboardInterrupt:
            print("\n正在停止...")
        finally:
            server.close()
            print("服务端已停止")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    server = RemoteServer(port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n服务端已停止")