#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端（修复版 - 防止键位卡死）
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
import atexit

LISTEN_PORT = 5000
FPS = 30
JPEG_QUALITY = 60
pyautogui.FAILSAFE = True  # 启用故障安全


class RemoteServer:
    def __init__(self, port=5000):
        self.port = port
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True
        self.active_keys = set()  # 记录按下的键
        self.lock = threading.Lock()

        # 注册退出清理
        atexit.register(self.cleanup_keys)

    def cleanup_keys(self):
        """清理所有按下的键"""
        print("\n正在清理按键状态...")
        with self.lock:
            for key in list(self.active_keys):
                try:
                    pyautogui.keyUp(key)
                    print(f"释放按键: {key}")
                except:
                    pass
            self.active_keys.clear()

    def release_all_modifiers(self):
        """释放所有修饰键"""
        modifiers = ['shift', 'ctrl', 'alt', 'shiftleft', 'ctrlleft', 'altleft']
        for key in modifiers:
            try:
                pyautogui.keyUp(key)
            except:
                pass

    def send_screen(self, conn):
        """发送屏幕画面"""
        print("📹 屏幕传输线程启动")
        frame_count = 0
        last_time = time.time()

        try:
            while self.running:
                img = ImageGrab.grab()
                frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                ret, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])

                if not ret:
                    continue

                data = jpg.tobytes()
                conn.sendall(struct.pack('>I', len(data)))
                conn.sendall(data)

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
                try:
                    conn.settimeout(1.0)
                    data = conn.recv(1024)
                    if not data:
                        break

                    cmd = data.decode('utf-8', 'ignore').strip()

                    if cmd.startswith("MOVE:"):
                        try:
                            _, x, y = cmd.split(":")
                            pyautogui.moveTo(int(float(x)), int(float(y)))
                        except:
                            pass

                    elif cmd == "CLICK_LEFT":
                        pyautogui.click()
                        print("左键点击")

                    elif cmd == "CLICK_RIGHT":
                        pyautogui.rightClick()
                        print("右键点击")

                    elif cmd == "SCROLL_UP":
                        pyautogui.scroll(1)
                        print("滚轮向上")

                    elif cmd == "SCROLL_DOWN":
                        pyautogui.scroll(-1)
                        print("滚轮向下")

                    elif cmd.startswith("KEY_DOWN:"):
                        key = cmd.replace("KEY_DOWN:", "").lower()
                        with self.lock:
                            if key not in self.active_keys:
                                pyautogui.keyDown(key)
                                self.active_keys.add(key)
                                print(f"按键按下: {key}")

                    elif cmd.startswith("KEY_UP:"):
                        key = cmd.replace("KEY_UP:", "").lower()
                        with self.lock:
                            if key in self.active_keys:
                                pyautogui.keyUp(key)
                                self.active_keys.discard(key)
                                print(f"按键释放: {key}")

                    elif cmd == "RESET_KEYS":
                        # 重置所有按键
                        self.cleanup_keys()
                        conn.send(b"OK")

                    elif cmd == "GET_SCREEN_SIZE":
                        screen = pyautogui.size()
                        conn.sendall(f"{screen.width}:{screen.height}".encode())

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"处理命令错误: {e}")

        except Exception as e:
            print(f"控制错误: {e}")
        finally:
            # 连接断开时清理该连接相关的按键
            self.cleanup_keys()
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
                try:
                    server.settimeout(1.0)
                    conn, addr = server.accept()
                    print(f"客户端已连接: {addr}")

                    try:
                        conn.settimeout(5)
                        room = conn.recv(1024).decode().strip()
                        if room == self.room_id:
                            conn.send(b"OK")
                            print("房间号验证通过")

                            # 重置按键状态
                            self.cleanup_keys()

                            threading.Thread(target=self.send_screen, args=(conn,), daemon=True).start()
                            threading.Thread(target=self.handle_control, args=(conn,), daemon=True).start()
                        else:
                            conn.send(b"ERROR")
                            conn.close()
                            print(f"房间号错误: {room}")
                    except:
                        conn.close()

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"接受连接错误: {e}")

        except KeyboardInterrupt:
            print("\n正在停止...")
        finally:
            self.running = False
            self.cleanup_keys()
            server.close()
            print("服务端已停止")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    server = RemoteServer(port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n服务端已停止")