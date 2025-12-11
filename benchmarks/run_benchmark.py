"""
QP-Sim Comprehensive Benchmark Runner
Executes simulations across a range of qubit counts and aggregates hardware metrics.
"""
import time
import os
import sys
import argparse
import csv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qiskit import QuantumCircuit

try:
    from qp_sim import QPagingSimulator
except ImportError:
    print("Error: qp_sim not found. Build with 'maturin develop --release'")
    sys.exit(1)

from system_monitor import SystemMonitor


def create_heavy_circuit(qubits):
    """Creates a stress-test circuit"""
    qc = QuantumCircuit(qubits)
    for i in range(qubits):
        qc.h(i)
    for i in range(qubits - 1):
        qc.cx(i, i + 1)
    for i in range(qubits):
        qc.rx(0.5, i)
    qc.measure_all()
    return qc


def run_experiment_suite(start_q, end_q, step):
    results_dir = "./bench_results"
    data_dir = "./bench_data"

    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    summary_file = os.path.join(results_dir, "benchmark_summary.csv")

    # Initialize summary CSV
    with open(summary_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "qubits",
            "theoretical_size_gb",
            "duration_s",
            "peak_rss_gb",  # Process RSS
            "peak_cache_gb",  # OS Page Cache
            "peak_disk_read_mb",
            "peak_disk_write_mb",
            "peak_gpu_util",
            "peak_gpu_mem_mb",
        ])

    print(f"=== Starting Benchmark Suite (Qubits: {start_q}-{end_q}, step: {step}) ===")
    print()

    for n in range(start_q, end_q + 1, step):
        print(f"--- Running {n} Qubits ---")
        theoretical_size = (2**n * 16) / (1024**3)
        print(f"State Vector: {theoretical_size:.4f} GB")

        run_dir = os.path.join(results_dir, f"q{n}")
        monitor = SystemMonitor(output_dir=run_dir, interval=0.1)
        monitor.start()
        time.sleep(1)

        try:
            qc = create_heavy_circuit(n)
            backend = QPagingSimulator(memory_limit="4GB", backing_store=data_dir)

            start_time = time.time()
            job = backend.run(qc)
            _ = job.result()
            duration = time.time() - start_time

            print(f"✓ Finished in {duration:.2f}s")

        except Exception as e:
            print(f"✗ Failed: {e}")
            import traceback
            traceback.print_exc()
            duration = 0
        finally:
            monitor.stop()
            metrics = monitor.get_peak_metrics()

            # Append to summary CSV
            with open(summary_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    n,
                    f"{theoretical_size:.4f}",
                    f"{duration:.4f}",
                    f"{metrics.get('peak_rss_gb', 0):.4f}",
                    f"{metrics.get('peak_cache_gb', 0):.4f}",
                    f"{metrics.get('peak_disk_read', 0):.2f}",
                    f"{metrics.get('peak_disk_write_mb', 0):.2f}",
                    f"{metrics.get('peak_gpu_util', 0):.1f}",
                    f"{metrics.get('peak_gpu_mem', 0):.2f}",
                ])

            print()

    print(f"=== Benchmark Suite Complete ===")
    print(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="QP-Sim Comprehensive Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default: 20-30 qubits, step 2
  python run_benchmark.py

  # Custom range
  python run_benchmark.py --start 14 --end 30 --step 2

  # Full range test
  python run_benchmark.py --start 14 --end 30 --step 2
        """
    )
    parser.add_argument("--start", type=int, default=20, help="Start qubit count (default: 20)")
    parser.add_argument("--end", type=int, default=30, help="End qubit count (default: 30)")
    parser.add_argument("--step", type=int, default=2, help="Step size (default: 2)")

    args = parser.parse_args()

    run_experiment_suite(args.start, args.end, args.step)
