"""
System Monitor for QP-Sim Benchmark
Records hardware metrics during simulation execution
"""
import time
import threading
import psutil
import csv
import os
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np

class SystemMonitor:
    def __init__(self, output_dir="./bench_results", interval=0.5):
        self.output_dir = output_dir
        self.interval = interval
        self.running = False
        self.thread = None
        self.data = {
            "timestamp": [],
            "cpu_percent": [],
            "ram_process_rss_gb": [],  # Process RSS (private memory)
            "ram_system_cache_gb": [],  # OS Page Cache (where mmap lives)
            "disk_read_mb": [],
            "disk_write_mb": [],
            "gpu_util": [],
            "gpu_mem_mb": [],
        }

        self.process = psutil.Process(os.getpid())

        # GPU Setup (NVIDIA)
        self.has_gpu = False
        self.nvml_handle = None
        try:
            try:
                import pynvml
            except ImportError:
                from nvidia_ml_py import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_name = pynvml.nvmlDeviceGetName(self.nvml_handle)
                # Decode bytes to string if necessary
                if isinstance(gpu_name, bytes):
                    gpu_name = gpu_name.decode('utf-8')
                self.has_gpu = True
                print(f"[Monitor] GPU Monitoring Active: {gpu_name}")
            else:
                print("[Monitor] No NVIDIA GPU devices found.")
        except ImportError:
            print("[Monitor] Warning: 'nvidia-ml-py' not installed. GPU monitoring disabled.")
            print("          Run: pip install nvidia-ml-py")
        except Exception as e:
            print(f"[Monitor] GPU Init Failed: {e}")

        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop)
        self.thread.daemon = True  # Ensure thread dies if main process dies
        self.thread.start()
        print("[Monitor] Background recording started...")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        print("[Monitor] Recording stopped.")

        # Only save individual files if output_dir is specified
        if self.output_dir:
            self.save_plot()
            self.save_csv()

    def get_peak_metrics(self):
        """Return summary stats for the session"""
        if not self.data["timestamp"]:
            return {}

        return {
            "peak_rss_gb": max(self.data["ram_process_rss_gb"]) if self.data["ram_process_rss_gb"] else 0,
            "peak_cache_gb": max(self.data["ram_system_cache_gb"]) if self.data["ram_system_cache_gb"] else 0,
            "avg_cpu_util": np.mean(self.data["cpu_percent"]) if self.data["cpu_percent"] else 0,
            "peak_disk_read": max(self.data["disk_read_mb"]) if self.data["disk_read_mb"] else 0,
            "peak_disk_write_mb": max(self.data["disk_write_mb"]) if self.data["disk_write_mb"] else 0,
            "peak_gpu_util": max(self.data["gpu_util"]) if self.has_gpu and self.data["gpu_util"] else 0,
            "peak_gpu_mem": max(self.data["gpu_mem_mb"]) if self.has_gpu and self.data["gpu_mem_mb"] else 0,
        }

    def _loop(self):
        start_time = time.time()

        # Initialize disk I/O counters
        disk_io_start = psutil.disk_io_counters()
        last_read = disk_io_start.read_bytes if disk_io_start else 0
        last_write = disk_io_start.write_bytes if disk_io_start else 0
        last_time = start_time
        time.sleep(0.1)  # Stabilize before first measurement

        while self.running:
            current_time = time.time()
            elapsed = current_time - start_time

            # CPU
            cpu = psutil.cpu_percent(interval=None)

            # Memory: Split RSS and Cache
            # RSS: Resident Set Size (non-swapped physical memory used by process)
            try:
                mem_info = self.process.memory_info()
                rss_gb = mem_info.rss / (1024**3)
            except Exception:
                rss_gb = 0

            # System-wide Cache (where mmap often hides)
            sys_mem = psutil.virtual_memory()
            if hasattr(sys_mem, 'cached'):
                cache_gb = (sys_mem.cached + getattr(sys_mem, 'buffers', 0)) / (1024**3)
            else:
                # Fallback for non-Linux systems
                cache_gb = (sys_mem.total - sys_mem.available) / (1024**3) - rss_gb

            # Disk I/O throughput
            disk_io = psutil.disk_io_counters()
            time_delta = current_time - last_time

            read_speed = 0
            write_speed = 0

            if time_delta > 0 and disk_io:
                read_speed = (disk_io.read_bytes - last_read) / (1024**2) / time_delta
                write_speed = (disk_io.write_bytes - last_write) / (1024**2) / time_delta
                last_read = disk_io.read_bytes
                last_write = disk_io.write_bytes

            last_time = current_time

            # GPU metrics (if available)
            gpu_util = 0
            gpu_mem = 0
            if self.has_gpu and self.nvml_handle is not None:
                try:
                    try:
                        import pynvml
                    except ImportError:
                        from nvidia_ml_py import pynvml
                    util = pynvml.nvmlDeviceGetUtilizationRates(self.nvml_handle)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(self.nvml_handle)
                    gpu_util = util.gpu
                    gpu_mem = mem.used / (1024**2)  # MB
                except Exception as e:
                    # Only print error once to avoid spam
                    if not hasattr(self, '_gpu_error_logged'):
                        print(f"[Monitor] GPU read error (will retry): {e}")
                        self._gpu_error_logged = True
                    gpu_util = 0
                    gpu_mem = 0

            # Record
            self.data["timestamp"].append(elapsed)
            self.data["cpu_percent"].append(cpu)
            self.data["ram_process_rss_gb"].append(rss_gb)
            self.data["ram_system_cache_gb"].append(cache_gb)
            self.data["disk_read_mb"].append(read_speed)
            self.data["disk_write_mb"].append(write_speed)
            self.data["gpu_util"].append(gpu_util)
            self.data["gpu_mem_mb"].append(gpu_mem)

            time.sleep(self.interval)

    def save_csv(self):
        if not self.data["timestamp"]:
            print("[Monitor] No data collected, skipping CSV save")
            return

        if not self.output_dir:
            return

        os.makedirs(self.output_dir, exist_ok=True)
        filename = os.path.join(self.output_dir, "metrics.csv")
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(self.data.keys())
            writer.writerows(zip(*self.data.values()))
        print(f"[Monitor] Data saved to {filename}")

    def save_plot(self):
        if not self.data["timestamp"]:
            print("[Monitor] No data collected, skipping plot")
            return

        if not self.output_dir:
            return

        os.makedirs(self.output_dir, exist_ok=True)

        # Create 4-panel plot
        fig, axes = plt.subplots(4, 1, figsize=(10, 16), sharex=True)
        t = self.data["timestamp"]

        # Memory breakdown: RSS vs Cache
        axes[0].plot(t, self.data["ram_process_rss_gb"], "b-", label="App RSS (Private)", linewidth=2)
        axes[0].plot(t, self.data["ram_system_cache_gb"], "c--", label="OS Page Cache (Shared)", linewidth=1.5)
        axes[0].set_ylabel("Memory (GB)")
        axes[0].set_title("Detailed Memory Usage")
        axes[0].grid(True)
        axes[0].legend(loc="upper left")

        # Disk I/O
        axes[1].plot(t, self.data["disk_read_mb"], "g-", label="Read (MB/s)", linewidth=2)
        axes[1].plot(t, self.data["disk_write_mb"], "y--", label="Write (MB/s)", alpha=0.5, linewidth=1)
        axes[1].set_ylabel("Disk I/O (MB/s)")
        axes[1].grid(True)
        axes[1].legend(loc="upper left")

        # CPU utilization
        axes[2].plot(t, self.data["cpu_percent"], "k-", label="CPU Util (%)", linewidth=2)
        axes[2].set_ylabel("CPU (%)")
        axes[2].grid(True)
        axes[2].legend(loc="upper left")

        # GPU utilization and memory
        # Always show GPU panel if GPU is detected
        if self.has_gpu:
            axes[3].plot(t, self.data["gpu_util"], "m-", label="GPU Util (%)", linewidth=2)
            ax3_twin = axes[3].twinx()
            ax3_twin.plot(t, self.data["gpu_mem_mb"], "r:", label="GPU Mem (MB)", linewidth=1.5)
            ax3_twin.set_ylabel("GPU Mem (MB)", color="r")
            axes[3].set_ylabel("GPU Util (%)", color="m")

            # Combine legends
            lines, labels = axes[3].get_legend_handles_labels()
            lines2, labels2 = ax3_twin.get_legend_handles_labels()
            axes[3].legend(lines + lines2, labels + labels2, loc="upper left")

            # Add note if utilization is 0
            if max(self.data["gpu_util"] + [0]) == 0:
                axes[3].text(0.02, 0.98, "Note: GPU util 0% (CPU-only computation)",
                           transform=axes[3].transAxes, fontsize=9,
                           verticalalignment='top', style='italic', alpha=0.7)
        else:
            axes[3].text(0.5, 0.5, "No GPU Detected", ha="center", va="center", transform=axes[3].transAxes)

        axes[-1].set_xlabel("Time (s)")
        axes[-1].grid(True)

        img_path = os.path.join(self.output_dir, "benchmark_profile.png")
        plt.tight_layout()
        plt.savefig(img_path, dpi=150)
        print(f"[Monitor] Plot saved to {img_path}")
        plt.close()
