# Qiskit Backend
from qiskit.providers import BackendV2, Options
from qiskit.transpiler import Target
from qiskit.result import Result
from qiskit.circuit import QuantumCircuit
import numpy as np
import os
import uuid

# Import our Rust Core
from .qp_sim_core import SimulatorController

class QPagingSimulator(BackendV2):
    """
    Q-Paging Backend for Qiskit.
    Offloads large state-vector simulation to an SSD-backed Rust engine.
    """
    def __init__(self, memory_limit="16GB", backing_store="./scratch_space"):
        super().__init__(name="qp_paging_simulator")
        self._memory_limit = memory_limit
        self._backing_store = backing_store
        
        # Ensure scratch directory exists
        if not os.path.exists(backing_store):
            os.makedirs(backing_store)
            
        # Define target (gates supported)
        self._target = Target()
        # In a real app, we would add_instruction for X, H, CX, etc.

    @property
    def target(self):
        return self._target

    @property
    def max_circuits(self):
        return 1

    @classmethod
    def _default_options(cls):
        return Options(shots=1024)

    def run(self, run_input, **options):
        """
        Run the circuit on the Rust Q-Paging Engine.
        """
        # 1. Handle Input (Single circuit for MVP)
        if isinstance(run_input, list):
            circuit = run_input[0]
        else:
            circuit = run_input

        # 2. Extract Circuit Info for Rust
        num_qubits = circuit.num_qubits
        
        # Parse Gates
        gate_names = []
        targets = []
        params = []
        
        for instruction in circuit.data:
            op = instruction.operation
            qubits = instruction.qubits
            
            # Map Qubit Objects to Indices
            q_indices = [circuit.find_bit(q).index for q in qubits]
            
            gate_names.append(op.name)
            targets.append(q_indices)
            params.append([float(p) for p in op.params])

        # 3. Initialize Rust Engine
        # Generate unique file for this run
        unique_filename = f"state_{uuid.uuid4()}.bin"
        file_path = os.path.join(self._backing_store, unique_filename)
        
        controller = SimulatorController(num_qubits, file_path)
        
        print(f"[Python] Offloading {num_qubits}-qubit circuit to Rust...")
        controller.initialize()
        
        # 4. Execute
        final_state = controller.run_circuit(gate_names, targets, params)
        
        # 5. Wrap Result (Simplified Mock Result for Qiskit)
        # In real world, we would format this as a proper Result object
        # with Counts or Statevector
        return JobWrapper(final_state)

class JobWrapper:
    def __init__(self, result_data):
        self._data = result_data
        
    def result(self):
        return self._data

