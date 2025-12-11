// Controller
use pyo3::prelude::*;

use crate::engine::memory::QuantumMemoryManager;
use crate::engine::circuit::{CircuitAnalyzer, GateOp};
use crate::engine::io::AsyncIoEngine;

#[pyclass]
pub struct SimulatorController {
    memory: Option<QuantumMemoryManager>, // Option allows taking ownership/dropping
    num_qubits: usize,
    backing_store: String,
}

#[pymethods]
impl SimulatorController {
    #[new]
    pub fn new(num_qubits: usize, backing_store: String) -> Self {
        Self {
            memory: None,
            num_qubits,
            backing_store,
        }
    }

    /// Phase 1: Initialize Memory
    pub fn initialize(&mut self) -> PyResult<()> {
        let mem = QuantumMemoryManager::new(self.num_qubits, &self.backing_store)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
        
        self.memory = Some(mem);
        println!("[Rust Core] Initialized {} Qubits on SSD: {}", self.num_qubits, self.backing_store);
        Ok(())
    }

    /// Phase 2: Execute Circuit (The Main Loop)
    /// Receives a list of gates from Python
    pub fn run_circuit(&mut self, gate_names: Vec<String>, targets: Vec<Vec<usize>>, params: Vec<Vec<f64>>) -> PyResult<Vec<f64>> {
        let _mem = self.memory.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Memory not initialized")
        })?;

        // 1. Convert to internal GateOp
        let mut ops = Vec::new();
        for i in 0..gate_names.len() {
            ops.push(GateOp {
                name: gate_names[i].clone(),
                targets: targets[i].clone(),
                params: params[i].clone(),
            });
        }

        // 2. Analyze (Lookahead)
        let analyzer = CircuitAnalyzer::new(self.num_qubits);
        let _schedule = analyzer.analyze(&ops);

        // 3. Setup IO
        let mut _io = AsyncIoEngine::new(128).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string())
        })?;

        println!("[Rust Core] Analyzed {} gates. Starting execution loop...", ops.len());

        // 4. Execution Loop (Simplified for MVP)
        // In real implementation:
        // for (idx, gate) in ops.iter().enumerate() {
        //     scheduler.ensure_pages(idx);
        //     kernels.apply_gate(gate, mem.as_mut_slice());
        // }

        // Return dummy expectation value for test
        Ok(vec![0.0, 0.0]) 
    }
}

