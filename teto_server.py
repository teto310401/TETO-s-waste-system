#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端（被控制端）
修复连接关闭异常
"""
import sys
import socket
import threading
import struct
import time
import ctypes
import platform
import traceback
from PIL import ImageGrab, Image
import io

TETO_PROTOCOL = b"teto_run"


class RemoteServer:
    def __init__(self, port=5000):
        self.port = port
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True
        self.local_mouse_time = 0
        self.screen_streaming = False
        self.screen_socket = None
        self.control_connections = []  # 存储控制连接
        self.screen_connections = []  # 存储屏幕连接
        self.lock = threading.Lock()  # 线程锁

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
            screenshot = ImageGrab.grab()
            img_buffer = io.BytesIO()
            screenshot.save(img_buffer, format='JPEG', quality=70, optimize=True)
            return img_buffer.getvalue()
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
            sock.sendall(struct.pack('>I', len(img_data)))
            sock.sendall(img_data)
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError) as e:
            print(f"发送屏幕帧失败: {e}")
            return False
        except Exception as e:
            print(f"发送屏幕帧异常: {e}")
            return False

    def _screen_stream_thread(self, sock):
        """屏幕传输线程，保持30帧速率"""
        print("屏幕传输线程启动，目标帧率: 30 FPS")
        frame_interval = 1.0 / 30.0

        while self.screen_streaming and self.running:
            try:
                # 检查socket是否还活着
                if not sock or sock.fileno() == -1:
                    print("屏幕传输socket已关闭")
                    break

                start_time = time.time()

                # 发送一帧
                if not self._send_screen_frame(sock):
                    break

                # 控制帧率
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
            except (socket.error, OSError) as e:
                print(f"屏幕传输线程socket错误: {e}")
                break
            except Exception as e:
                print(f"屏幕传输线程异常: {e}")
                break

        print("屏幕传输线程结束")
        self.screen_streaming = False

    def handle_control_client(self, sock, addr):
        """处理控制连接（鼠标控制）"""
        print(f"控制客户端已连接: {addr}")

        # 添加到连接列表
        with self.lock:
            self.control_connections.append(sock)

        try:
            sock.settimeout(5)  # 设置超时
            while self.running:
                try:
                    data = sock.recv(1024).decode()
                    if not data:
                        break

                    if data.startswith("MOVE:"):
                        if time.time() - self.local_mouse_time > 2:
                            parts = data[5:].split(",")
                            if len(parts) == 2:
                                dx, dy = map(int, parts)
                                ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
                    elif data.startswith("CLICK:"):
                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                    elif data.startswith("START_STREAM:"):
                        if not self.screen_streaming:
                            self.screen_streaming = True
                            sock.send(b"STREAM_OK")
                        else:
                            sock.send(b"STREAM_ALREADY")
                    elif data.startswith("STOP_STREAM:"):
                        self.screen_streaming = False
                        sock.send(b"STREAM_STOPPED")
                except socket.timeout:
                    continue
                except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                    print(f"控制连接socket错误: {e}")
                    break
                except Exception as e:
                    print(f"处理控制数据异常: {e}")
                    break
        except Exception as e:
            print(f"控制客户端处理异常: {e}")
        finally:
            # 清理连接
            with self.lock:
                if sock in self.control_connections:
                    self.control_connections.remove(sock)
            try:
                sock.close()
            except:
                pass
            print(f"控制连接断开: {addr}")

    def handle_screen_client(self, sock, addr):
        """处理屏幕传输连接"""
        print(f"屏幕传输客户端已连接: {addr}")

        # 添加到连接列表
        with self.lock:
            self.screen_connections.append(sock)

        try:
            # 等待控制线程设置标志
            last_check = time.time()
            while self.running:
                if self.screen_streaming:
                    self._screen_stream_thread(sock)
                    break
                else:
                    # 每秒检查一次，避免空转
                    if time.time() - last_check > 1:
                        # 发送心跳包检查连接
                        try:
                            sock.send(b'')
                        except:
                            break
                        last_check = time.time()
                    time.sleep(0.1)
        except Exception as e:
            print(f"屏幕客户端处理异常: {e}")
        finally:
            # 清理连接
            with self.lock:
                if sock in self.screen_connections:
                    self.screen_connections.remove(sock)
            try:
                sock.close()
            except:
                pass
            print(f"屏幕传输连接断开: {addr}")

    def accept_connections(self, control_socket, screen_socket):
        """接受连接的线程"""

        # 启动控制连接接受线程
        def accept_control():
            while self.running:
                try:
                    control_socket.settimeout(1)
                    conn, addr = control_socket.accept()
                    # 验证协议
                    try:
                        conn.settimeout(5)
                        proto = conn.recv(len(TETO_PROTOCOL))
                        if proto != TETO_PROTOCOL:
                            conn.close()
                            continue
                        room = conn.recv(1024).decode().replace("ROOM:", "")
                        if room == self.room_id:
                            conn.send(b"OK")
                            # 启动处理线程
                            threading.Thread(
                                target=self.handle_control_client,
                                args=(conn, addr),
                                daemon=True
                            ).start()
                        else:
                            conn.send(b"ERROR")
                            conn.close()
                    except socket.timeout:
                        conn.close()
                    except Exception as e:
                        print(f"控制连接接受异常: {e}")
                        conn.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"控制socket接受异常: {e}")
                    break

        # 启动屏幕连接接受线程
        def accept_screen():
            while self.running:
                try:
                    screen_socket.settimeout(1)
                    conn, addr = screen_socket.accept()
                    # 验证协议
                    try:
                        conn.settimeout(5)
                        proto = conn.recv(len(TETO_PROTOCOL))
                        if proto != TETO_PROTOCOL:
                            conn.close()
                            continue
                        room = conn.recv(1024).decode().replace("ROOM:", "")
                        if room == self.room_id:
                            conn.send(b"OK")
                            # 启动处理线程
                            threading.Thread(
                                target=self.handle_screen_client,
                                args=(conn, addr),
                                daemon=True
                            ).start()
                        else:
                            conn.send(b"ERROR")
                            conn.close()
                    except socket.timeout:
                        conn.close()
                    except Exception as e:
                        print(f"屏幕连接接受异常: {e}")
                        conn.close()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"屏幕socket接受异常: {e}")
                    break

        # 启动接受线程
        control_thread = threading.Thread(target=accept_control, daemon=True)
        screen_thread = threading.Thread(target=accept_screen, daemon=True)
        control_thread.start()
        screen_thread.start()

        # 等待线程结束
        control_thread.join()
        screen_thread.join()

    def start(self):
        print(f"===== 远程服务端启动 =====")
        print(f"房间号: {self.room_id}")
        print(f"控制端口: {self.port}")
        print(f"屏幕端口: {self.port + 1}")
        print(f"协议: TETO_RUN")
        print("按 Ctrl+C 停止服务")
        print("=========================\n")

        # 创建socket
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(("0.0.0.0", self.port))
        control_socket.listen(5)

        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        screen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        screen_socket.bind(("0.0.0.0", self.port + 1))
        screen_socket.listen(5)

        print("服务已启动，等待连接...")

        try:
            # 接受连接
            self.accept_connections(control_socket, screen_socket)
        except KeyboardInterrupt:
            print("\n正在停止服务...")
        finally:
            self.running = False
            # 关闭所有连接
            with self.lock:
                for conn in self.control_connections:
                    try:
                        conn.close()
                    except:
                        pass
                for conn in self.screen_connections:
                    try:
                        conn.close()
                    except:
                        pass

            control_socket.close()
            screen_socket.close()
            print("服务端已停止")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    server = RemoteServer(port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n服务端已停止")
    except Exception as e:
        print(f"服务端错误: {e}")
        traceback.print_exc()