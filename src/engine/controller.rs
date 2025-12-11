// Controller Integration with Phase 2 Prefetching and Phase 3 Features
use pyo3::prelude::*;

use std::collections::hash_map::DefaultHasher;
use std::fs;
use std::hash::{Hash, Hasher};

use crate::engine::circuit::{AccessSchedule, CircuitAnalyzer, GateOp};
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
    // [Phase 3] Caching Mechanism for VQA scenarios
    cached_schedule: Option<AccessSchedule>,
    last_circuit_hash: u64,
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
            cached_schedule: None,
            last_circuit_hash: 0,
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

    /// Create a checkpoint snapshot of the current state
    pub fn create_checkpoint(&self, checkpoint_path: String) -> PyResult<()> {
        if let Some(mem) = &self.memory {
            // Flush memory to disk
            mem.snapshot()
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

            // Copy backing file to checkpoint location
            // Note: Copies entire file. Use COW (reflink) in production for efficiency.
            fs::copy(&self.backing_store, &checkpoint_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

            println!("[Rust Core] Checkpoint created at {}", checkpoint_path);
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Memory not initialized",
            ))
        }
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

        // Convert inputs and compute hash for cache lookup
        let mut ops = Vec::new();
        let mut hasher = DefaultHasher::new();

        for i in 0..gate_names.len() {
            // Hash structure (name + targets), ignore parameters
            gate_names[i].hash(&mut hasher);
            targets[i].hash(&mut hasher);

            ops.push(GateOp {
                name: gate_names[i].clone(),
                targets: targets[i].clone(),
                params: params[i].clone(),
            });
        }
        let current_hash = hasher.finish();

        // Analyze circuit or reuse cached schedule (VQA optimization)
        let schedule = if self.last_circuit_hash == current_hash && self.cached_schedule.is_some() {
            println!("[Rust Core] Cache HIT. Reusing Analysis Schedule.");
            self.cached_schedule.as_ref().unwrap().clone()
        } else {
            println!("[Rust Core] Cache MISS. Running Circuit Analysis...");
            let analyzer = CircuitAnalyzer::new(self.num_qubits);
            let schedule = analyzer.analyze(&ops);

            self.cached_schedule = Some(schedule.clone());
            self.last_circuit_hash = current_hash;
            schedule
        };

        // Initialize IO engine with high concurrency queue
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

            // Safety check: OS handles page faults automatically via mmap
            // If prefetch is slow, mmap will block on access until pages are loaded

            // Apply gate operation
            // Pages should be prefetched from iteration (i - lookahead_depth)
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
