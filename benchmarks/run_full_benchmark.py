"""
Full Benchmark with System Monitoring
Runs QP-Sim simulation while recording hardware metrics
Supports single qubit count or range (14-30)
"""
import time
import os
import sys
import argparse

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qiskit import QuantumCircuit

try:
    from qp_sim import QPagingSimulator
    HAS_QP = True
except ImportError:
    HAS_QP = False
    print("Error: qp_sim not found. Please install the package first.")
    sys.exit(1)

from system_monitor import SystemMonitor


def create_heavy_circuit(qubits):
    """Create stress-test circuit with superposition, entanglement, and rotation"""
    qc = QuantumCircuit(qubits)
    for i in range(qubits):
        qc.h(i)
    for i in range(qubits - 1):
        qc.cx(i, i + 1)
    for i in range(qubits):
        qc.rx(0.5, i)
    qc.measure_all()
    return qc


def run_single_experiment(n_qubits, monitor=None):
    """Run a single benchmark experiment"""
    if monitor is None:
        monitor = SystemMonitor(interval=0.1)
        monitor.start()
        time.sleep(0.5)
        should_stop = True
    else:
        should_stop = False

    try:
        print(f"=== QP-Sim Benchmark: {n_qubits} Qubits ===")
        print(f"State vector size: {(2**n_qubits * 16) / (1024**3):.2f} GB")
        print()

        qc = create_heavy_circuit(n_qubits)

        backend = QPagingSimulator(memory_limit="4GB", backing_store="./bench_data")

        print("Running Simulation...")
        start_time = time.time()
        job = backend.run(qc)
        _ = job.result()  # Wait for completion
        duration = time.time() - start_time

        print(f"✓ Completed in {duration:.2f} seconds")
        print()
        return duration

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if should_stop:
            monitor.stop()


def run_range_experiment(start_qubits=14, end_qubits=30, step=2):
    """Run benchmarks for a range of qubit counts"""
    results = []

    print("=" * 70)
    print("QP-Sim Range Benchmark (14-30 qubits)")
    print("=" * 70)
    print()
    print(f"Testing qubit counts: {start_qubits} to {end_qubits} (step {step})")
    print()

    for n_qubits in range(start_qubits, end_qubits + 1, step):
        monitor = SystemMonitor(
            output_dir=f"./bench_results/qubits_{n_qubits}",
            interval=0.1
        )
        monitor.start()
        time.sleep(0.5)

        duration = run_single_experiment(n_qubits, monitor)
        monitor.stop()

        results.append({
            'qubits': n_qubits,
            'duration': duration,
            'state_vector_gb': (2**n_qubits * 16) / (1024**3)
        })

        time.sleep(1)  # Delay between runs

    # Print summary
    print()
    print("=" * 70)
    print("Benchmark Summary")
    print("=" * 70)
    print(f"{'Qubits':<8} | {'State Vector (GB)':<18} | {'Duration (s)':<15} | {'Status':<10}")
    print("-" * 70)
    for r in results:
        status = "✓ Success" if r['duration'] is not None else "✗ Failed"
        duration_str = f"{r['duration']:.2f}" if r['duration'] else "N/A"
        print(f"{r['qubits']:<8} | {r['state_vector_gb']:<18.4f} | {duration_str:<15} | {status:<10}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="QP-Sim Benchmark with System Monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single qubit count
  python run_full_benchmark.py 25

  # Range of qubits (14-30, step 2)
  python run_full_benchmark.py --range 14 30

  # Custom range with step
  python run_full_benchmark.py --range 14 30 --step 4
        """
    )
    parser.add_argument(
        'qubits',
        type=int,
        nargs='?',
        default=None,
        help='Single qubit count to test (default: 30)'
    )
    parser.add_argument(
        '--range',
        nargs=2,
        type=int,
        metavar=('START', 'END'),
        help='Test range of qubits from START to END'
    )
    parser.add_argument(
        '--step',
        type=int,
        default=2,
        help='Step size for range testing (default: 2)'
    )

    args = parser.parse_args()

    if not os.path.exists("./bench_data"):
        os.makedirs("./bench_data")

    print("=" * 70)
    print("QP-Sim Full Benchmark with System Monitoring")
    print("=" * 70)
    print()

    if args.range:
        # Range mode
        start, end = args.range
        if start < 14 or end > 30:
            print("Warning: Recommended range is 14-30 qubits")
        if start > end:
            print("Error: Start must be <= End")
            sys.exit(1)

        print(f"Configuration:")
        print(f"  - Range: {start} to {end} qubits (step {args.step})")
        print(f"  - Memory limit: 4GB (forcing out-of-core)")
        print()

        results = run_range_experiment(start, end, args.step)

        print()
        print("=" * 70)
        print("Range Benchmark Complete!")
        print("=" * 70)
        print("Check ./bench_results/qubits_*/ for individual results:")
        print("  - benchmark_profile.png (system resource plots)")
        print("  - metrics_*.csv (raw data)")
    else:
        # Single qubit mode
        n_qubits = args.qubits if args.qubits is not None else 30

        print(f"Configuration:")
        print(f"  - Qubits: {n_qubits}")
        print(f"  - Expected state vector: {(2**n_qubits * 16) / (1024**3):.2f} GB")
        print(f"  - Memory limit: 4GB (forcing out-of-core)")
        print()

        run_single_experiment(n_qubits)

        print()
        print("=" * 70)
        print("Benchmark Complete!")
        print("=" * 70)
        print("Check ./bench_results/ for:")
        print("  - benchmark_profile.png (system resource plots)")
        print("  - metrics_*.csv (raw data)")
