"""
Basic test script for QP-Sim
Demonstrates usage with a 30-qubit circuit that would crash standard Qiskit Aer
"""
from qiskit import QuantumCircuit
from qp_sim import QPagingSimulator

# 建立一個 30 Qubits 的電路 (在普通筆電上跑 Qiskit Aer 會當機)
qc = QuantumCircuit(30)
qc.h(0)
for i in range(29):
    qc.cx(i, i+1)

# 使用 Q-Paging
backend = QPagingSimulator(backing_store="./qp_data")
job = backend.run(qc)
print("Simulation finished via Rust Core!")

