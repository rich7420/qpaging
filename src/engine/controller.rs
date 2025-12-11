// Controller Integration with Phase 2 Prefetching
use pyo3::prelude::*;

use crate::engine::circuit::{CircuitAnalyzer, GateOp};
use crate::engine::io::AsyncIoEngine;
use crate::engine::kernels;
use crate::engine::memory::QuantumMemoryManager;

#[pyclass]
pub struct SimulatorController {
    memory: Option<QuantumMemoryManager>, // Option allows taking ownership/dropping
    num_qubits: usize,
    backing_store: String,
    // Tuning parameter: How many gates to look ahead?
    // For MVP, lookahead = 1 is sufficient to demonstrate mechanism
    lookahead_depth: usize,
}

#[pymethods]
impl SimulatorController {
    #[new]
    pub fn new(num_qubits: usize, backing_store: String) -> Self {
        Self {
            memory: None,
            num_qubits,
            backing_store,
            lookahead_depth: 1,
        }
    }

    /// Phase 1: Initialize Memory
    pub fn initialize(&mut self) -> PyResult<()> {
        let mem = QuantumMemoryManager::new(self.num_qubits, &self.backing_store)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

        self.memory = Some(mem);
        println!(
            "[Rust Core] Initialized {} Qubits on SSD: {}",
            self.num_qubits, self.backing_store
        );
        Ok(())
    }

    /// Phase 2: Execute Circuit (The Main Loop)
    /// Receives a list of gates from Python
    pub fn run_circuit(
        &mut self,
        gate_names: Vec<String>,
        targets: Vec<Vec<usize>>,
        params: Vec<Vec<f64>>,
    ) -> PyResult<Vec<f64>> {
        let mem = self.memory.as_mut().ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Memory not initialized")
        })?;

        // 1. Convert inputs
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
        let schedule = analyzer.analyze(&ops);

        // 3. Initialize IO Engine (Queue Depth 256 for high concurrency)
        let mut io_engine = AsyncIoEngine::new(256).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to init io_uring: {}", e))
        })?;

        println!("[Rust Core] Starting execution loop with Deterministic Prefetching...");

        // 4. Execution Loop
        for i in 0..ops.len() {
            let op = &ops[i];

            // --- A. PREFETCH STEP (Phase 2) ---
            // Look ahead to future gates and trigger IO
            if i + self.lookahead_depth < ops.len() {
                let future_idx = i + self.lookahead_depth;
                if let Some(future_pages) = schedule.timeline.get(&future_idx) {
                    // Submit async prefetch request
                    let _submitted = io_engine
                        .submit_prefetch(future_pages, mem.as_ptr())
                        .unwrap_or(0);

                    // Debug output for first few gates
                    if i < 3 {
                        println!(
                            "  [Prefetch] Triggered for Gate {} (ahead of execution)",
                            future_idx
                        );
                    }
                }
            }

            // Cleanup completed IO tasks (don't let CQ overflow)
            io_engine.reap_completions();

            // --- B. COMPUTATION STEP (Phase 1) ---
            // At this point, pages for Gate 'i' should have been requested
            // during loop iteration 'i - lookahead_depth'.
            // OS handles the actual mapping.
            let matrix = kernels::get_matrix(&op.name, &op.params);

            kernels::apply_single_qubit_gate(
                mem.as_mut_slice(),
                self.num_qubits,
                op.targets[0],
                matrix,
            );
        }

        println!("[Rust Core] Execution finished.");
        Ok(vec![0.0, 0.0])
    }
}
