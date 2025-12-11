"""
Basic test script for QP-Sim
Demonstrates usage with a 30-qubit circuit that would crash standard Qiskit Aer
"""
from qiskit import QuantumCircuit
from qp_sim import QPagingSimulator

# Create a 30-qubit circuit (would crash standard Qiskit Aer on typical laptops)
qc = QuantumCircuit(30)
qc.h(0)
for i in range(29):
    qc.cx(i, i+1)

# Use Q-Paging backend
backend = QPagingSimulator(backing_store="./qp_data")
job = backend.run(qc)
print("Simulation finished via Rust Core!")

