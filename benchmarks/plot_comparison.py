"""
Comparison Plot Generator for QP-Sim Benchmark Results
Generates publication-quality figures from benchmark_summary.csv
"""
import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

def plot_benchmark_results():
    results_path = "./bench_results/benchmark_summary.csv"
    if not os.path.exists(results_path):
        print("Error: summary file not found. Run 'run_benchmark.py' first.")
        print(f"Expected path: {os.path.abspath(results_path)}")
        return

    try:
        df = pd.read_csv(results_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if df.empty:
        print("Error: Summary file is empty")
        return

    # Create 2x2 subplot layout
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("QP-Sim Performance Scaling Analysis", fontsize=16, fontweight="bold")

    # Memory breakdown: RSS vs Cache vs Theoretical
    ax1.plot(df["qubits"], df["peak_rss_gb"], "b-o", label="Process RSS (Private)", linewidth=2, markersize=8)
    ax1.plot(df["qubits"], df["peak_cache_gb"], "c-s", label="OS Page Cache (Shared)", linewidth=1.5, markersize=6, alpha=0.7)
    ax1.plot(df["qubits"], df["theoretical_size_gb"], "r--", label="Theoretical Size", alpha=0.5, linewidth=2)

    ax1.set_title("Memory Usage Breakdown", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Qubits", fontsize=11)
    ax1.set_ylabel("Memory (GB)", fontsize=11)
    ax1.set_yscale("log")
    ax1.grid(True, which="both", ls="-", alpha=0.2)
    ax1.legend(fontsize=10)

    # I/O throughput scaling
    ax2.plot(
        df["qubits"],
        df["peak_disk_read_mb"],
        "g-s",
        label="Peak Disk Read",
        linewidth=2,
        markersize=8,
    )
    ax2.set_title("I/O Throughput Scaling", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Qubits", fontsize=11)
    ax2.set_ylabel("Read Speed (MB/s)", fontsize=11)
    ax2.grid(True, alpha=0.2)
    ax2.legend(fontsize=10)

    # Runtime scaling
    ax3.plot(
        df["qubits"],
        df["duration_s"],
        "k-^",
        label="Execution Time",
        linewidth=2,
        markersize=8,
    )
    ax3.set_title("Runtime Scaling", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Qubits", fontsize=11)
    ax3.set_ylabel("Time (seconds)", fontsize=11)
    ax3.set_yscale("log")
    ax3.grid(True, which="both", ls="-", alpha=0.2)
    ax3.legend(fontsize=10)

    # GPU analysis (if data exists)
    if 'peak_gpu_util' in df.columns and df['peak_gpu_util'].max() > 0:
        ax4.plot(df["qubits"], df["peak_gpu_util"], "m-d", label="GPU Util %", linewidth=2, markersize=8)
        ax4_twin = ax4.twinx()
        ax4_twin.plot(df["qubits"], df["peak_gpu_mem_mb"], "r:", label="GPU Mem (MB)", linewidth=1.5)
        ax4_twin.set_ylabel("Memory (MB)", color="r")
        ax4.set_ylabel("Utilization (%)", color="m")
        ax4.set_title("GPU Offloading Performance", fontsize=12, fontweight="bold")
        ax4.set_xlabel("Qubits", fontsize=11)

        # Combine legends
        lines, labels = ax4.get_legend_handles_labels()
        lines2, labels2 = ax4_twin.get_legend_handles_labels()
        ax4.legend(lines + lines2, labels + labels2, fontsize=10)
        ax4.grid(True, alpha=0.2)
    else:
        ax4.text(0.5, 0.5, "No GPU Activity Recorded", ha="center", va="center", transform=ax4.transAxes, fontsize=12)
        ax4.set_title("GPU Analysis", fontsize=12, fontweight="bold")
        ax4.set_xlabel("Qubits", fontsize=11)

    output_img = "./bench_results/final_analysis.png"
    plt.tight_layout()
    plt.savefig(output_img, dpi=300, bbox_inches="tight")
    print(f"✓ Analysis plots saved to {os.path.abspath(output_img)}")
    print("\n=== Summary Statistics ===")
    print(f"Qubit range: {df['qubits'].min()} - {df['qubits'].max()}")
    if 'peak_rss_gb' in df.columns:
        print(f"Peak RSS: {df['peak_rss_gb'].max():.2f} GB")
    if 'peak_cache_gb' in df.columns:
        print(f"Peak Cache: {df['peak_cache_gb'].max():.2f} GB")
    print(f"Peak disk read: {df['peak_disk_read_mb'].max():.2f} MB/s")
    print(f"Max execution time: {df['duration_s'].max():.2f} s")


if __name__ == "__main__":
    plot_benchmark_results()
