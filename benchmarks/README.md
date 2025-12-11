# QP-Sim Benchmark Suite

This benchmark suite compares QP-Sim (SSD-based) against Qiskit Aer (RAM-based) to demonstrate the "Memory Wall" breakthrough.

## Prerequisites

Install required dependencies:

```bash
uv pip install psutil matplotlib numpy qiskit-aer pynvml
```

Or using pip:

```bash
pip install psutil matplotlib numpy qiskit-aer pynvml
```

## Benchmark Scripts

### 1. Comprehensive Benchmark Suite (`run_benchmark.py`) - **Recommended**

Runs experiments across a range of qubit counts and generates aggregated results:

```bash
cd benchmarks
uv run python run_benchmark.py --start 14 --end 30 --step 2
```

This will:
- Test qubit counts from 14 to 30 (step 2)
- Record hardware metrics for each run
- Generate `benchmark_summary.csv` with aggregated data
- Create individual result directories (`q14/`, `q16/`, etc.)

### 2. Comparison Plot Generator (`plot_comparison.py`)

Generates publication-quality figures from benchmark results:

```bash
cd benchmarks
uv run python plot_comparison.py
```

This reads `benchmark_summary.csv` and creates `final_analysis.png` with:
- **Memory Wall Analysis**: RAM usage vs theoretical size
- **I/O Throughput Scaling**: Disk read speed across qubit counts
- **Runtime Scaling**: Execution time scaling

### 3. Single Run with Monitoring (`run_full_benchmark.py`)

Runs a single simulation with detailed monitoring:

```bash
# Single qubit count
uv run python run_full_benchmark.py 25

# Range test
uv run python run_full_benchmark.py --range 14 30 --step 2
```

### 4. Throughput Comparison (`run_throughput.py`)

Compares QP-Sim vs Qiskit Aer execution times:

```bash
uv run python run_throughput.py
```

## Expected Results

The benchmark will test circuits from 20 to 34 qubits:

1. **Qubits < 26**: Qiskit Aer (RAM) is faster than QP-Sim
   - Normal behavior: RAM bandwidth >> SSD bandwidth
   - Q-Paging has overhead for prefetching

2. **Qubits ≈ 28-30**: Qiskit Aer starts slowing down or crashes (OOM)
   - OS begins swapping to disk
   - QP-Sim continues running stably

3. **Qubits > 30**: Qiskit Aer cannot run
   - QP-Sim continues running, time increases exponentially but **does not crash**
   - This demonstrates "Q-Paging breaks the Memory Wall"

## Output

### Comprehensive Benchmark (`run_benchmark.py`)
- `benchmark_summary.csv`: Aggregated metrics for all qubit counts
  - Columns: qubits, theoretical_size_gb, duration_s, peak_ram_gb, avg_cpu_util, peak_disk_read_mb, etc.
- Individual result directories (`q14/`, `q16/`, etc.):
  - `benchmark_profile.png`: System resource plots for that qubit count
  - `metrics.csv`: Raw timestamped data

### Comparison Plots (`plot_comparison.py`)
- `final_analysis.png`: Three-panel publication-quality figure:
  - **Left**: Breaking the Memory Wall (RAM vs Theoretical)
  - **Middle**: I/O Throughput Scaling
  - **Right**: Runtime Scaling (log scale)

### Single Run (`run_full_benchmark.py`)
- `benchmark_profile.png`: Detailed system resource plots
- `metrics.csv`: Raw timestamped data

## Interpretation

### Throughput Plot
- **Red line (Qiskit Aer)**: Stops at ~28-30 qubits (Memory Wall)
- **Blue line (QP-Sim)**: Continues beyond 30 qubits (Memory Wall broken)

### System Profile Plot
The `benchmark_profile.png` demonstrates:

1. **RAM Usage (Flatline)**:
   - Should plateau at memory limit (e.g., 4GB)
   - Proves out-of-core mechanism is working
   - Stays well below physical RAM limit

2. **Disk Read Throughput (Spikes)**:
   - Should show high read rates (e.g., 1000+ MB/s) during simulation
   - Proves `io_uring` prefetching is active
   - Demonstrates deterministic prefetch working

3. **CPU Utilization**:
   - Should remain high, showing computation and I/O overlap
   - Proves parallel execution is effective

These plots are the core evidence for the paper's evaluation section.
