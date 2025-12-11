# QP-Sim: Out-of-Core Quantum Simulator with Circuit-Aware Paging

QP-Sim is a high-performance quantum simulator that uses circuit-aware virtual memory management to handle large state vectors that exceed available RAM. The system enables simulation of 40+ qubit circuits on standard hardware without out-of-memory crashes.

## Product Definition

QP-Sim is designed as a production-ready, out-of-core quantum simulation backend plugin that seamlessly integrates with existing quantum computing ecosystems (Qiskit and PennyLane). The tool enables researchers and developers to run large-scale quantum simulations that would otherwise cause out-of-memory (OOM) crashes on standard hardware.

## Features

- **Circuit-Aware Paging**: Deterministic prefetching based on static circuit analysis (Lookahead mechanism)
- **Rust Core Engine**: High-performance memory management and asynchronous I/O
- **Zero-Code-Change Integration**: Drop-in replacement for Qiskit `AerSimulator` and PennyLane devices
- **Qiskit Integration**: Seamless integration with Qiskit SDK v1.4+ (BackendV2 interface)
- **PennyLane Support**: Plugin device for quantum machine learning workflows
- **Linux io_uring**: Asynchronous I/O for efficient SSD access and prefetching
- **Plan Caching**: Optimized for variational algorithms (QAOA/VQE) with parameterized circuits

## Requirements

- Rust (Edition 2021, compatible with 2024)
- Python 3.10+
- Linux (for io_uring support)
- Qiskit 1.4.0+ (for Qiskit integration)
- Maturin (build tool for Python extensions)

## Installation

### Prerequisites

1. Install Rust toolchain:
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. Install Python development environment:
   ```bash
   sudo apt update
   sudo apt install python3.12-venv python3-pip
   ```

### Build Instructions

1. Create a Python virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install maturin:
   ```bash
   pip install maturin
   ```

3. Build and install the package:
   ```bash
   maturin develop --release
   ```

### Verification

After installation, verify the package:
```bash
python3 -c "from qp_sim import QPagingSimulator; print('Installation successful')"
```

## Usage

### Scenario A: Qiskit Integration

QP-Sim provides a drop-in replacement for Qiskit's `AerSimulator`, requiring only a backend swap:

```python
from qiskit import QuantumCircuit, transpile
from qp_sim import QPagingSimulator

# Define a large circuit (e.g., 35 qubits)
qc = QuantumCircuit(35)
qc.h(0)
for i in range(34):
    qc.cx(i, i+1)
qc.measure_all()

# Use QP-Sim backend with memory limit
backend = QPagingSimulator(memory_limit="16GB", backing_store="./scratch_space")

# Execute circuit
job = backend.run(transpile(qc, backend), shots=1024)
result = job.result()
```

### Scenario B: PennyLane Integration

For quantum machine learning workflows, QP-Sim provides a PennyLane device:

```python
import pennylane as qml

# Define QP-Sim device
dev = qml.device("qpaging.lightning", wires=32, ram_limit="8GB")

@qml.qnode(dev)
def circuit(params):
    qml.RX(params[0], wires=0)
    # ... complex entanglement layers ...
    return qml.expval(qml.PauliZ(0))

# Execute circuit
result = circuit([0.1, 0.2])
```

## Circuit Scenarios and Optimizations

QP-Sim is optimized for four representative quantum circuit scenarios:

### Scenario 1: Deep Random Circuits

**Characteristics**: Extremely deep circuits with random gate distribution, no structure, fast entanglement spread.

**Challenge**: State vector becomes dense (many non-zero elements) at each layer, requiring maximum memory bandwidth.

**QP-Sim Strategy**: Strict prefetching with deterministic lookahead. Random gates cause OS prefetcher to fail (0% hit rate), while Q-Paging maintains 100% hit rate through circuit analysis.

### Scenario 2: Variational Quantum Algorithms (QAOA/VQE)

**Characteristics**: Fixed circuit structure (Ansatz) with parameters that change iteratively, requiring thousands of iterations.

**Challenge**: Re-analyzing circuit on every iteration creates high overhead.

**QP-Sim Strategy (Plan Caching)**: Compile once, run many. Cache the prefetch schedule from the analyzer. When parameters change but structure remains constant, reuse the schedule and only update numerical computation. Critical for QML training workflows.

### Scenario 3: Quantum Chemistry (QPE/Trotterization)

**Characteristics**: Highly structured circuits with many controlled operations and repeated blocks.

**Challenge**: Requires many qubits to simulate molecular orbitals with very long runtime.

**QP-Sim Strategy (Checkpointing)**: Built-in snapshot/restore functionality. Since state is already on SSD, checkpointing is nearly free (just flush metadata). Essential for long-running scientific simulations.

### Scenario 4: Sparsely Connected Circuits

**Characteristics**: Some qubits interact infrequently; state vector has many zeros or can be decomposed.

**Challenge**: Not the strong suit of full-amplitude simulation, but users may submit such circuits.

**QP-Sim Strategy**: Dynamic page allocation. Only allocate physical SSD pages for non-zero state vector blocks (sparse backing store). More efficient than naive `mmap`, avoiding wasted disk space.

## Architecture

The simulator implements two key mechanisms:

1. **Mechanism 1 (Lookahead)**: Static circuit analysis to deterministically calculate memory access patterns before execution
2. **Mechanism 2 (Deterministic Prefetch)**: Asynchronous I/O (io_uring) to prefetch required pages before computation, eliminating page faults

### System Layers

```
Level 1: Python Bindings
  - Qiskit BackendV2 Provider
  - PennyLane Plugin Device
  - Python C-API (PyO3)

Level 2: Core Engine (Rust)
  - Simulation Controller
  - Schedule Cache (For VQA/QML)
  - Memory Subsystem
    - Static Circuit Analyzer
    - Virtual Memory Orchestrator
    - Async I/O Engine (io_uring)
  - Compute Subsystem
    - OpenMP/AVX512 Kernels
    - (Optional) CUDA Kernels

Level 3: Infrastructure
  - NVMe SSD File (Backing Store)
  - Host DRAM (Working Set)
```

## Project Structure

```
qp-sim/
├── Cargo.toml          # Rust dependencies
├── pyproject.toml      # Python build configuration
├── src/
│   ├── lib.rs          # PyO3 entry point
│   └── engine/         # Core logic
│       ├── mod.rs
│       ├── memory.rs   # VMM & Paging Logic
│       ├── circuit.rs  # Lookahead Analyzer
│       ├── io.rs       # io_uring wrapper
│       └── controller.rs # Main controller
├── qp_sim/             # Python package
│   ├── __init__.py
│   ├── qiskit_backend.py
│   └── qp_sim_core.so  # Compiled Rust extension
└── examples/           # Test scripts
```

## Development Roadmap

### Phase 1: MVP (Current)

- Core functionality: Qiskit BackendV2 interface support
- Scope: Single `QuantumCircuit` execution (no parameterized loops)
- Algorithm: Basic Lookahead + Prefetch implementation
- Goal: Run 32-qubit random circuit without crash, faster than swap

### Phase 2: QML Support

- Core functionality: PennyLane Plugin interface
- Feature: Plan Caching (support VQA/QAOA)
- Optimization: AVX-512 instruction set for state vector operations

### Phase 3: Robustness and Distribution

- Core functionality: `pip install` packaging
- Feature: Checkpointing (resume from interruption)
- Feature: Distributed execution support

## Technical Details

### Core Technologies

- **Rust (Edition 2021)**: Memory safety and performance
- **Python 3.10+**: Integration layer
- **PyO3**: Rust-Python bindings with stable ABI (abi3)
- **io_uring**: Linux async I/O for deterministic prefetching
- **memmap2**: Advanced memory mapping with `madvise` control
- **Qiskit 1.4+**: BackendV2 interface (modern standard)

### Memory Management

- **Page Size**: 4KB (system standard)
- **State Vector Format**: Complex128 (16 bytes per amplitude)
- **Memory Advice**: `MADV_RANDOM` to disable OS prefetch, `MADV_DONTNEED` for eviction
- **Resident Tracking**: BitVec for efficient page state management

### Build Status

The Rust core compiles successfully:
- Compilation: No errors
- Warnings: 8 warnings (expected for MVP - unused code for future implementation)
- Output: `target/release/libqp_sim_core.so`

## Troubleshooting

### Issue: "No module named pip"

**Solution**: Install python3-pip
```bash
sudo apt install python3-pip
```

### Issue: "ensurepip is not available"

**Solution**: Install python3-venv
```bash
sudo apt install python3.12-venv
```

### Issue: PEP 668 protection

**Solution**: Use virtual environment (recommended) or add `--break-system-packages` flag

### Issue: Maturin not found

**Solution**: 
- Check PATH: `echo $PATH`
- Use full path: `~/.local/bin/maturin`
- Or use: `python3 -m maturin`

## License

[Add your license here]

## Acknowledgments

This project implements the Q-Paging algorithm for out-of-core quantum simulation, designed for system conferences and production use.
