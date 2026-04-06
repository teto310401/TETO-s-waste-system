#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端（被控制端）
修复房间号显示问题
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
        # 生成6位房间号
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True
        self.local_mouse_time = 0
        self.screen_streaming = False
        self.screen_socket = None
        self.control_connections = []
        self.screen_connections = []
        self.lock = threading.Lock()

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
        """屏幕传输线程"""
        print("屏幕传输线程启动，目标帧率: 30 FPS")
        frame_interval = 1.0 / 30.0

        while self.screen_streaming and self.running:
            try:
                if not sock or sock.fileno() == -1:
                    print("屏幕传输socket已关闭")
                    break

                start_time = time.time()

                if not self._send_screen_frame(sock):
                    break

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
        """处理控制连接"""
        print(f"控制客户端已连接: {addr}")

        with self.lock:
            self.control_connections.append(sock)

        try:
            sock.settimeout(5)
            while self.running:
                try:
                    data = sock.recv(1024).decode()
                    if not data:
                        break

                    print(f"收到控制命令: {data[:50]}")  # 调试输出

                    if data.startswith("MOVE:"):
                        if time.time() - self.local_mouse_time > 2:
                            parts = data[5:].split(",")
                            if len(parts) == 2:
                                dx, dy = map(int, parts)
                                ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
                    elif data.startswith("CLICK:"):
                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
                    elif data == "START_STREAM:":
                        if not self.screen_streaming:
                            self.screen_streaming = True
                            sock.send(b"STREAM_OK")
                            print("视频流已启动")
                        else:
                            sock.send(b"STREAM_ALREADY")
                    elif data == "STOP_STREAM:":
                        self.screen_streaming = False
                        sock.send(b"STREAM_STOPPED")
                        print("视频流已停止")
                except socket.timeout:
                    continue
                except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                    print(f"控制连接错误: {e}")
                    break
                except Exception as e:
                    print(f"处理控制数据异常: {e}")
                    break
        except Exception as e:
            print(f"控制客户端处理异常: {e}")
        finally:
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

        with self.lock:
            self.screen_connections.append(sock)

        try:
            while self.running:
                if self.screen_streaming:
                    self._screen_stream_thread(sock)
                    break
                else:
                    time.sleep(0.1)
        except Exception as e:
            print(f"屏幕客户端处理异常: {e}")
        finally:
            with self.lock:
                if sock in self.screen_connections:
                    self.screen_connections.remove(sock)
            try:
                sock.close()
            except:
                pass
            print(f"屏幕传输连接断开: {addr}")

    def start(self):
        print("=" * 50)
        print("Teto 远程服务端")
        print("=" * 50)
        print(f"房间号: {self.room_id}")
        print(f"控制端口: {self.port}")
        print(f"屏幕端口: {self.port + 1}")
        print("=" * 50)
        print("请在客户端输入以上房间号进行连接")
        print("按 Ctrl+C 停止服务\n")

        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(("0.0.0.0", self.port))
        control_socket.listen(5)

        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        screen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        screen_socket.bind(("0.0.0.0", self.port + 1))
        screen_socket.listen(5)

        print("服务已启动，等待连接...\n")

        try:
            while self.running:
                # 接受控制连接
                try:
                    control_socket.settimeout(1)
                    conn, addr = control_socket.accept()

                    # 验证协议
                    try:
                        conn.settimeout(5)
                        proto = conn.recv(len(TETO_PROTOCOL))
                        if proto != TETO_PROTOCOL:
                            print(f"协议错误，拒绝连接: {addr}")
                            conn.close()
                            continue

                        room_data = conn.recv(1024).decode().strip()
                        # 解析房间号
                        if room_data.startswith("ROOM:"):
                            room = room_data[5:].strip()
                            print(f"收到房间号: '{room}', 期望: '{self.room_id}'")

                            if room == self.room_id:
                                conn.send(b"OK")
                                print(f"✓ 控制客户端验证成功: {addr}")
                                threading.Thread(
                                    target=self.handle_control_client,
                                    args=(conn, addr),
                                    daemon=True
                                ).start()
                            else:
                                conn.send(b"ERROR")
                                print(f"✗ 房间号错误: {addr} (收到:{room}, 期望:{self.room_id})")
                                conn.close()
                        else:
                            print(f"房间号格式错误: {room_data}")
                            conn.close()
                    except socket.timeout:
                        print(f"验证超时: {addr}")
                        conn.close()
                    except Exception as e:
                        print(f"验证异常: {e}")
                        conn.close()

                except socket.timeout:
                    pass
                except Exception as e:
                    if self.running:
                        print(f"接受连接异常: {e}")

                # 接受屏幕连接（简单处理，不在这里阻塞）
                try:
                    screen_socket.settimeout(0.1)
                    conn, addr = screen_socket.accept()

                    # 验证协议
                    try:
                        conn.settimeout(5)
                        proto = conn.recv(len(TETO_PROTOCOL))
                        if proto != TETO_PROTOCOL:
                            conn.close()
                            continue

                        room_data = conn.recv(1024).decode().strip()
                        if room_data.startswith("ROOM:"):
                            room = room_data[5:].strip()
                            if room == self.room_id:
                                conn.send(b"OK")
                                print(f"✓ 屏幕客户端验证成功: {addr}")
                                threading.Thread(
                                    target=self.handle_screen_client,
                                    args=(conn, addr),
                                    daemon=True
                                ).start()
                            else:
                                conn.send(b"ERROR")
                                conn.close()
                        else:
                            conn.close()
                    except:
                        conn.close()
                except socket.timeout:
                    pass
                except:
                    pass

        except KeyboardInterrupt:
            print("\n正在停止服务...")
        finally:
            self.running = False
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