#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程服务端（被控制端）
"""
import sys
import socket
import threading
import struct
import time
import ctypes
import platform

TETO_PROTOCOL = b"teto_run"

class RemoteServer:
    def __init__(self, port=5000):
        self.port = port
        self.room_id = str(100000 + int(time.time()) % 900000)
        self.running = True
        self.local_mouse_time = 0

    def _check_mouse(self):
        if platform.system() != "Windows":
            return True
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self.local_mouse_time = time.time()
        except:
            pass

    def handle_client(self, sock):
        print(f"客户端已连接")
        try:
            while self.running:
                data = sock.recv(1024).decode()
                if not data: break
                if data.startswith("MOVE:"):
                    if time.time() - self.local_mouse_time > 2:
                        dx, dy = map(int, data[5:].split(","))
                        ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
                elif data.startswith("CLICK:"):
                    ctypes.windll.user32.mouse_event(0x0002,0,0,0,0)
                    ctypes.windll.user32.mouse_event(0x0004,0,0,0,0)
        except:
            pass
        print("连接断开")

    def start(self):
        print(f"===== 远程服务端启动 =====")
        print(f"房间号: {self.room_id}")
        print(f"端口: {self.port}")
        print(f"协议: TETO_RUN")
        print("=========================\n")

        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", self.port))
        s.listen(5)

        while self.running:
            try:
                conn, addr = s.accept()
                proto = conn.recv(len(TETO_PROTOCOL))
                if proto != TETO_PROTOCOL:
                    conn.close()
                    continue
                room = conn.recv(1024).decode().replace("ROOM:", "")
                if room == self.room_id:
                    conn.send(b"OK")
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                else:
                    conn.send(b"ERROR")
                    conn.close()
            except:
                break

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    server = RemoteServer(port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("服务端已停止")