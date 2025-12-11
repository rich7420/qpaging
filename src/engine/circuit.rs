// Circuit Analyzer
use std::collections::HashMap;
use bitvec::prelude::*;

/// Represents a simple Quantum Gate for analysis
#[derive(Debug, Clone)]
pub struct GateOp {
    pub name: String,
    pub targets: Vec<usize>,
    pub params: Vec<f64>,
}

/// The "Global Access Schedule"
pub struct AccessSchedule {
    /// Maps Gate Index -> BitMap of Required Pages
    /// Using BitVec is much more memory efficient than Vec<usize>
    pub timeline: HashMap<usize, BitVec>,
}

pub struct CircuitAnalyzer {
    page_size: usize,
    total_bytes: usize,
    element_size: usize, // 16 bytes for Complex128
}

impl CircuitAnalyzer {
    pub fn new(num_qubits: usize) -> Self {
        Self {
            page_size: 4096,
            total_bytes: (1 << num_qubits) * 16,
            element_size: 16,
        }
    }

    /// The "Lookahead" logic
    pub fn analyze(&self, gates: &[GateOp]) -> AccessSchedule {
        let mut timeline = HashMap::new();
        println!("[Analyzer] Analyzing {} gates for Access Patterns...", gates.len());
        
        for (idx, gate) in gates.iter().enumerate() {
            let required_pages = self.get_pages_for_gate(gate);
            timeline.insert(idx, required_pages);
        }
        
        AccessSchedule { timeline }
    }

    /// Core Logic: Bit manipulation to find touched pages
    fn get_pages_for_gate(&self, gate: &GateOp) -> BitVec {
        let total_pages = self.total_bytes / self.page_size;
        let mut pages = bitvec![usize, Lsb0; 0; total_pages];
        
        // For MVP, handling single qubit gates
        if gate.targets.is_empty() {
            return pages;
        }
        
        let target_qubit = gate.targets[0];
        
        let stride_elements = 1 << target_qubit;
        let stride_bytes = stride_elements * self.element_size;
        
        // --- SCENARIO A: Low Qubits (Dense / Sequential Access) ---
        // If the stride is smaller than a page (e.g., qubits 0-7),
        // the gate operations happen entirely within local memory blocks.
        // It effectively touches EVERY page.
        if stride_bytes < self.page_size {
            pages.fill(true); // Mark all pages as needed
            return pages;
        }
        
        // --- SCENARIO B: High Qubits (Strided Access) ---
        // If stride is larger than a page (e.g., qubit 20),
        // we touch a block of pages, skip a block, touch a block...
        // This is where Q-Paging beats the OS.
        
        // Block size in bytes = 2 * stride_bytes
        // Structure: [ Active Region (stride_bytes) | Inactive Region (stride_bytes) ]
        let pages_per_stride = stride_bytes / self.page_size;
        let pages_per_block = pages_per_stride * 2;
        
        // Iterate through blocks and mark the first half of each block
        // Optimized: We iterate by page indices
        for block_start in (0..total_pages).step_by(pages_per_block) {
            // Mark the "Active" half
            for i in 0..pages_per_stride {
                if block_start + i < total_pages {
                    pages.set(block_start + i, true);
                }
            }
        }
        
        pages
    }
}

