"""
Benchmark Suite for QP-Sim
Compares Qiskit Aer (RAM-based) vs QP-Sim (SSD-based) performance
"""
import time
import os
import sys

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not found. Memory tracking disabled.")

try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib/numpy not found. Plotting disabled.")

from qiskit import QuantumCircuit, transpile

try:
    from qiskit_aer import AerSimulator
    HAS_AER = True
except ImportError:
    HAS_AER = False
    print("Warning: qiskit-aer not found. Skipping baseline comparison.")

try:
    from qp_sim import QPagingSimulator
    HAS_QP = True
except ImportError:
    HAS_QP = False
    print("Error: qp_sim not found. Please install the package first.")
    sys.exit(1)


def get_memory_usage():
    """Returns current process memory usage in MB"""
    if HAS_PSUTIL:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    return 0.0


def create_random_circuit(num_qubits, depth=10):
    """Creates a moderately deep circuit to stress test memory access"""
    qc = QuantumCircuit(num_qubits)
    # Simple entanglement pattern
    for _ in range(depth):
        for i in range(num_qubits):
            qc.rx(0.5, i)
        for i in range(0, num_qubits - 1, 2):
            qc.cx(i, i + 1)
    qc.measure_all()
    return qc


def run_benchmark():
    qubit_ranges = range(20, 35, 2)  # 20, 22, ..., 34

    results = {
        "qubits": [],
        "aer_time": [],
        "qp_time": [],
        "qp_peak_mem": [],
    }

    print(f"{'Qubits':<8} | {'Aer (s)':<12} | {'QP-Sim (s)':<12} | {'QP Mem (MB)':<12} | {'Status':<15}")
    print("-" * 70)

    for n in qubit_ranges:
        qc = create_random_circuit(n)
        results["qubits"].append(n)

        # Baseline: Qiskit Aer
        aer_time = float('nan')
        if HAS_AER:
            if n <= 28:  # Skip larger qubits to prevent OOM
                try:
                    backend_aer = AerSimulator()
                    t_qc = transpile(qc, backend_aer)

                    start = time.time()
                    job = backend_aer.run(t_qc, shots=10)  # Low shots for speed
                    _ = job.result()
                    aer_time = time.time() - start
                except Exception as e:
                    print(f"Aer crashed at {n} qubits: {e}")
                    aer_time = float('nan')
            else:
                aer_time = float('nan')

        results["aer_time"].append(aer_time)

        # QP-Sim test
        qp_time = float('nan')
        qp_mem = 0.0
        try:
            backend_qp = QPagingSimulator(memory_limit="4GB", backing_store="./bench_data")
            t_qc = qc

            start = time.time()
            job = backend_qp.run(t_qc, shots=10)
            _ = job.result()
            qp_time = time.time() - start
            qp_mem = get_memory_usage()
            results["qp_peak_mem"].append(qp_mem)

        except Exception as e:
            print(f"QP-Sim failed at {n} qubits: {e}")
            results["qp_peak_mem"].append(0.0)

        results["qp_time"].append(qp_time)

        # Print status
        aer_str = f"{aer_time:.4f}" if aer_time == aer_time else "OOM/Skip"
        qp_str = f"{qp_time:.4f}" if qp_time == qp_time else "Fail"
        mem_str = f"{qp_mem:.1f}" if HAS_PSUTIL else "N/A"
        status = "Done"
        if aer_time != aer_time and qp_time == qp_time:
            status = "QP Wins!"
        print(f"{n:<8} | {aer_str:<12} | {qp_str:<12} | {mem_str:<12} | {status:<15}")

    return results


def plot_results(results):
    if not HAS_MATPLOTLIB:
        print("Skipping plot generation (matplotlib not available)")
        return

    qubits = results["qubits"]

    plt.figure(figsize=(10, 6))

    # Plot Aer
    aer_times = [t if t == t else None for t in results["aer_time"]]
    plt.plot(qubits, aer_times, 'r-o', label='Qiskit Aer (RAM)', linewidth=2, markersize=8)

    # Plot QP-Sim
    qp_times = [t if t == t else None for t in results["qp_time"]]
    plt.plot(qubits, qp_times, 'b-^', label='QP-Sim (SSD/Q-Paging)', linewidth=2, markersize=8)

    plt.yscale('log')
    plt.xlabel('Number of Qubits', fontsize=12)
    plt.ylabel('Execution Time (s) [Log Scale]', fontsize=12)
    plt.title('Quantum Simulation Scalability: RAM vs SSD', fontsize=14, fontweight='bold')
    plt.grid(True, which="both", ls="-", alpha=0.3)
    plt.legend(fontsize=11)

    # Mark memory wall
    plt.axvline(x=30, color='k', linestyle='--', alpha=0.5, linewidth=2)
    plt.text(30.5, plt.ylim()[0] * 2, '~16GB RAM Limit', rotation=90, fontsize=10)

    plt.tight_layout()
    plt.savefig('benchmark_throughput.png', dpi=150)
    print("\nPlot saved to benchmark_throughput.png")


if __name__ == "__main__":
    if not os.path.exists("./bench_data"):
        os.makedirs("./bench_data")

    print("=" * 70)
    print("QP-Sim Benchmark Suite")
    print("=" * 70)
    print()

    data = run_benchmark()

    print()
    print("=" * 70)
    print("Benchmark Complete")
    print("=" * 70)

    if HAS_MATPLOTLIB:
        plot_results(data)
