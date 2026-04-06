#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto 远程客户端（控制端）
"""
import sys
import socket
import tkinter as tk
import threading

TETO_PROTOCOL = b"teto_run"

class RemoteClient:
    def __init__(self, ip, room_id, port=5000):
        self.ip = ip
        self.room = room_id
        self.port = port
        self.sock = None
        self.root = None
        self.last_x = None
        self.last_y = None

    def connect(self):
        self.sock = socket.socket()
        self.sock.settimeout(10)
        self.sock.connect((self.ip, self.port))
        self.sock.send(TETO_PROTOCOL)
        self.sock.send(f"ROOM:{self.room}".encode())
        res = self.sock.recv(1024).decode()
        if res != "OK":
            print("房间号错误")
            return False
        print("连接成功！")
        return True

    def on_mouse(self, e):
        if self.last_x is not None:
            dx = e.x - self.last_x
            dy = e.y - self.last_y
            self.sock.send(f"MOVE:{dx},{dy}".encode())
        self.last_x = e.x
        self.last_y = e.y

    def on_click(self, e):
        self.sock.send(b"CLICK:1")

    def start_gui(self):
        self.root = tk.Tk()
        self.root.title("Teto 远程控制")
        self.root.geometry("800x600")
        canvas = tk.Canvas(self.root, bg="black", cursor="cross")
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.bind("<Motion>", self.on_mouse)
        canvas.bind("<Button-1>", self.on_click)
        self.root.mainloop()

    def run(self):
        if not self.connect():
            return
        self.start_gui()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python teto_client.py IP 房间号 [端口]")
        sys.exit(1)
    ip = sys.argv[1]
    room = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    client = RemoteClient(ip, room, port)
    try:
        client.run()
    except KeyboardInterrupt:
        print("客户端已退出")