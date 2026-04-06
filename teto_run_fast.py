#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teto Run Fast - 主程序（CMD控制台）
版本: 5.1 旗舰版
功能: 命令行调度、系统优化、病毒查杀、调用服务端/客户端
"""
import os
import sys
import subprocess
import time
import json
import ctypes
import platform
import threading
from datetime import datetime

# 依赖检查
PSUTIL_AVAILABLE = False
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠️ psutil未安装，部分功能受限")

# 配置文件
CONFIG_FILE = "teto_config.json"
WHITELIST_FILE = "teto_whitelist.json"
BLACKLIST_FILE = "teto_blacklist.json"
LOG_FILE = "teto_run_fast.log"

class TetoRunFast:
    def __init__(self):
        self.running = True
        self.config = self._load_json(CONFIG_FILE, self._get_default_config())
        self.whitelist = self._load_json(WHITELIST_FILE, {"processes": []})
        self.blacklist = self._load_json(BLACKLIST_FILE, {"processes": []})
        self.is_admin = self._check_admin()
        self._show_logo()

    def _show_logo(self):
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
        print("\033[90m功能: 内存优化 | CPU优化 | 网络优化 | 远程操控\033[0m\n")

    def _check_admin(self):
        if platform.system() == "Windows":
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                return False
        return os.geteuid() == 0

    def _get_default_config(self):
        return {
            "auto_optimize_interval": 30,
            "server_port": 8080,
            "file_transfer_port": 9000,
            "remote_port": 5000
        }

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default
        return default

    def log(self, msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log = f"[{ts}] [{level}] {msg}"
        if level == "WARNING":
            print(f"\033[93m{log}\033[0m")
        elif level == "ERROR":
            print(f"\033[91m{log}\033[0m")
        elif level == "SUCCESS":
            print(f"\033[92m{log}\033[0m")
        else:
            print(log)

    # ==================== 系统优化 ====================
    def optimize_memory(self):
        self.log("开始优化内存...")
        import gc, tempfile, shutil
        gc.collect()
        cleaned = 0
        temp_dirs = [tempfile.gettempdir()]
        for d in temp_dirs:
            if os.path.exists(d):
                for i in os.listdir(d):
                    try:
                        p = os.path.join(d, i)
                        if os.path.isfile(p):
                            os.remove(p)
                        else:
                            shutil.rmtree(p, ignore_errors=True)
                        cleaned +=1
                    except:
                        pass
        self.log(f"内存优化完成，清理{cleaned}个文件", "SUCCESS")

    def boost_cpu(self):
        self.log("设置CPU高性能模式...")
        if platform.system() == "Windows":
            subprocess.run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True)
        self.log("CPU优化完成", "SUCCESS")

    def optimize_network(self):
        self.log("优化网络...")
        if platform.system() == "Windows":
            cmds = [
                ["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"],
                ["ipconfig", "/flushdns"]
            ]
            for c in cmds:
                subprocess.run(c, capture_output=True)
        self.log("网络优化完成", "SUCCESS")

    # ==================== 远程操控调用 ====================
    def start_server(self, port=5000):
        """启动远程服务端（被控制）"""
        self.log(f"启动远程服务端，端口:{port}")
        subprocess.run(["start","cmd","/k","python teto_server.py",str(port)],shell=True)
        time.sleep(1)
        self.log("服务端启动完成", "SUCCESS")

    def start_client(self, ip, room_id, port=5000):
        """启动远程客户端（控制对方）"""
        self.log(f"连接远程:{ip}:{port} 房间号:{room_id}")
        subprocess.run([sys.executable, "teto_client.py", ip, room_id, str(port)])

    # ==================== CMD命令行 ====================
    def run_cmd(self):
        self.log("Teto CMD已启动，输入help查看帮助", "SUCCESS")
        while self.running:
            try:
                cmd = input("\n\033[91mTeto-CMD>\033[0m ").strip().lower()
                if not cmd: continue

                if cmd in ["exit", "quit"]:
                    self.running = False
                    break

                elif cmd == "help":
                    self._show_help()

                elif cmd == "optimize":
                    subprocess.run(["start","cmd","/k","python teto_run_CPU.py"],shell=True)
                    self.optimize_memory()
                    self.boost_cpu()
                    self.optimize_network()

                elif cmd.startswith("create-room"):
                    port = int(cmd.split()[1]) if len(cmd.split())>1 else 5000
                    self.start_server(port)

                elif cmd.startswith("join-room"):
                    parts = cmd.split()
                    if len(parts)>=3:
                        ip = parts[1]
                        room = parts[2]
                        port = int(parts[3]) if len(parts)>3 else 5000
                        self.start_client(ip, room, port)

                elif cmd == "status":
                    self.show_status()

                else:
                    os.system(cmd)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.log(f"错误:{e}", "ERROR")

    def show_status(self):
        print("\n===== 系统状态 =====")
        if PSUTIL_AVAILABLE:
            print(f"CPU:{psutil.cpu_percent(1)}%")
            print(f"内存:{psutil.virtual_memory().percent}%")
        print(f"管理员权限:{self.is_admin}")
        print("===================\n")

    def _show_help(self):
        print("""
===== Teto CMD 帮助 =====
optimize        - 全面系统优化
create-room [端口] - 创建远程房间（被控制）
join-room IP 房间号 [端口] - 加入房间（控制对方）
status          - 查看系统状态
exit/quit       - 退出
=======================
""")

    def run(self):
        self.log("主程序启动完成", "SUCCESS")
        self.run_cmd()

def main():
    if platform.system() == "Windows" and not ctypes.windll.shell32.IsUserAnAdmin():
        print("请求管理员权限...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return

    if not PSUTIL_AVAILABLE:
        print("安装依赖...")
        subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "mss", "pillow"])
        return

    app = TetoRunFast()
    app.run()

if __name__ == "__main__":
    main()