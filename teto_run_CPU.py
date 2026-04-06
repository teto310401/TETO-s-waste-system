import psutil
import time
import gc
import platform
import subprocess
import os
import threading
from datetime import datetime


class TetoRunCPU:
    auto_gc_running = False
    auto_gc_thread = None
    auto_gc_cmd_process = None

    @staticmethod
    def help():
        print("""
        
            ========================================
                 Teto CMD 帮助面板
            ========================================
            cpu          - 查看CPU使用率
            memory       - 查看内存信息
            disk         - 查看磁盘信息
            network      - 查看网络信息
            system       - 查看系统信息
            gc           - 手动清理内存（显示清理详情）
            auto_gc      - 开启自动GC（弹出新CMD窗口，每5秒清理一次）
            stop_gc      - 停止自动GC并关闭新窗口
            help         - 显示此帮助
            clear        - 清屏
            exit         - 退出程序
            ========================================
            
        """)

    @staticmethod
    def your_dev():
        print(" ")
        print("========================================================")
        print("\033[91m __________   _________   __________     ________\033[0m")
        print("\033[91m|____  ____| |   ______| |____  ____|  / ________ \\ \033[0m")
        print("\033[91m    |  |     |  |______      |  |      | |      | | \033[0m")
        print("\033[91m    |  |     |   ______|     |  |      | |      | | \033[0m")
        print("\033[91m    |  |     |  |______      |  |      | |______| | \033[0m")
        print("\033[91m    |__|     |_________|     |__|      \\_________/ \033[0m")
        print("========================================================")
        print(" ")

    @staticmethod
    def get_cpu_usage():
        psutil.cpu_percent(interval=None)
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"CPU使用率: {cpu_percent}%")
        print(f"CPU核心数: {psutil.cpu_count()} 逻辑核心")
        print(f"物理核心数: {psutil.cpu_count(logical=False)}")
        return cpu_percent

    @staticmethod
    def get_memory_info():
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        print(f"总内存: {mem.total / (1024 ** 3):.2f} GB")
        print(f"已用内存: {mem.used / (1024 ** 3):.2f} GB")
        print(f"可用内存: {mem.available / (1024 ** 3):.2f} GB")
        print(f"内存使用率: {mem.percent}%")
        print(f"交换分区: {swap.used / (1024 ** 3):.2f} GB / {swap.total / (1024 ** 3):.2f} GB")

    @staticmethod
    def get_disk_info():
        partitions = psutil.disk_partitions()
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                print(" ")
                print(f"磁盘 {partition.device} - {partition.mountpoint}")
                print(f"  总容量: {usage.total / (1024 ** 3):.2f} GB")
                print(f"  已用: {usage.used / (1024 ** 3):.2f} GB")
                print(f"  可用: {usage.free / (1024 ** 3):.2f} GB")
                print(f"  使用率: {usage.percent}%")
                print(" ")
            except PermissionError:
                continue

    @staticmethod
    def get_network_info():
        net_io = psutil.net_io_counters()
        print(" ")
        print(f"发送字节: {net_io.bytes_sent / (1024 ** 2):.2f} MB")
        print(f"接收字节: {net_io.bytes_recv / (1024 ** 2):.2f} MB")
        print(f"发送包数: {net_io.packets_sent}")
        print(f"接收包数: {net_io.packets_recv}")
        print(" ")

        net_addrs = psutil.net_if_addrs()
        print("\n网络接口:")
        for interface, addrs in net_addrs.items():
            for addr in addrs:
                if addr.family == 2:
                    print(f"  {interface}: {addr.address}")

    @staticmethod
    def get_system_info():
        print(" ")
        print(f"系统: {platform.system()} {platform.release()}")
        print(f"系统版本: {platform.version()}")
        print(f"处理器: {platform.processor()}")
        print(f"主机名: {platform.node()}")
        print(f"Python版本: {platform.python_version()}")
        print(f"开机时间: {datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"运行中的进程数: {len(psutil.pids())}")
        print(" ")

    @staticmethod
    def manual_gc():
        """手动GC - 显示清理详情"""
        print("\n[手动GC] 开始清理内存...")

        mem_before = psutil.virtual_memory().used
        gc_before = gc.get_count()

        collected = gc.collect()

        mem_after = psutil.virtual_memory().used
        mem_freed = mem_before - mem_after

        print("\n")
        print(f"[手动GC] 清理完成！")
        print(f"  - 回收的对象数量: {collected}")
        print(f"  - 释放的内存: {mem_freed / (1024 ** 2):.2f} MB")
        print(f"  - GC各代计数变化: {gc_before} -> {gc.get_count()}")
        print(f"  - 当前内存使用率: {psutil.virtual_memory().percent}%")
        print("[手动GC] 清理结束\n")

    @staticmethod
    def auto_gc_worker():
        """在新CMD窗口中运行自动GC"""
        # 创建Python脚本内容
        gc_script = '''
import psutil
import gc
import time
import os
from datetime import datetime

print("=" * 60)
print("         自动GC监控窗口 - TETO系统")
print("=" * 60)
print("此窗口将每5秒自动清理内存")
print("关闭此窗口即可停止自动GC")
print("=" * 60)

running = True

while running:
    try:
        # 记录清理前的状态
        mem_before = psutil.virtual_memory().used
        gc_before = gc.get_count()

        # 执行GC
        collected = gc.collect()

        # 计算清理结果
        mem_after = psutil.virtual_memory().used
        mem_freed = mem_before - mem_after

        # 显示清理信息
        print("\\n" + "-" * 50)
        print(f"[自动GC @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"  - 回收的对象数量: {collected}")
        print(f"  - 释放的内存: {mem_freed / (1024**2):.2f} MB")

        if collected > 0:
            print(f"  - 清理的垃圾类型:")
            print(f"      • 未引用的对象")
            print(f"      • 循环引用")
            print(f"      • 无法访问的内存块")

        print(f"  - GC各代计数: {gc.get_count()}")
        print(f"  - 当前内存使用率: {psutil.virtual_memory().percent}%")
        print("-" * 50)

        # 等待5秒
        for _ in range(5):
            time.sleep(1)

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"错误: {e}")

print("\\n自动GC已停止，你可以关闭此窗口")
time.sleep(2)
'''

        # 创建临时脚本文件
        script_path = os.path.join(os.environ['TEMP'], 'teto_auto_gc.py')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(gc_script)

        # 在新CMD窗口中运行脚本
        if platform.system() == 'Windows':
            # Windows: 打开新的CMD窗口
            TetoRunCPU.auto_gc_cmd_process = subprocess.Popen(
                ['start', 'cmd', '/k', 'python', script_path],
                shell=True
            )

    @staticmethod
    def start_auto_gc():
        """启动自动GC（弹出新CMD窗口）"""
        if TetoRunCPU.auto_gc_running:
            print("[自动GC] 已经在运行中！")
            return

        TetoRunCPU.auto_gc_running = True
        print("[自动GC] 正在启动新窗口...")

        # 在新线程中启动新窗口，避免阻塞
        thread = threading.Thread(target=TetoRunCPU.auto_gc_worker, daemon=True)
        thread.start()
        print("[自动GC] 新CMD窗口已弹出，每5秒自动清理内存")
        print("[自动GC] 关闭新窗口或输入 'stop_gc' 即可停止")

    @staticmethod
    def stop_auto_gc():
        """停止自动GC并关闭新窗口"""
        if not TetoRunCPU.auto_gc_running:
            print("[自动GC] 未在运行！")
            return

        TetoRunCPU.auto_gc_running = False

        # 关闭新CMD窗口
        if TetoRunCPU.auto_gc_cmd_process:
            try:
                TetoRunCPU.auto_gc_cmd_process.terminate()
                print("[自动GC] 已关闭新窗口")
            except:
                pass

        print("[自动GC] 已停止")

    @staticmethod
    def clear_screen():
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def run():
        while True:
            n = input("\033[91mTETO-CPU>\033[0m ")
            n = str(n).strip().lower()

            if n == "help":
                TetoRunCPU.help()
            elif n == "cpu":
                TetoRunCPU.get_cpu_usage()
            elif n == "memory":
                TetoRunCPU.get_memory_info()
            elif n == "disk":
                TetoRunCPU.get_disk_info()
            elif n == "network":
                TetoRunCPU.get_network_info()
            elif n == "system":
                TetoRunCPU.get_system_info()
            elif n == "gc":
                TetoRunCPU.manual_gc()
            elif n == "auto_gc":
                TetoRunCPU.start_auto_gc()
            elif n == "stop_gc":
                TetoRunCPU.stop_auto_gc()
            elif n == "clear":
                TetoRunCPU.clear_screen()
                TetoRunCPU.your_dev()
            elif n == "exit":
                if TetoRunCPU.auto_gc_running:
                    TetoRunCPU.stop_auto_gc()
                break
            elif n == "":
                continue
            else:
                print(f"未知命令: '{n}'，输入 'help' 查看可用命令")


if __name__ == "__main__":
    TetoRunCPU.your_dev()
    TetoRunCPU.run()