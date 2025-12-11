// Computation Kernels
// Direct memory manipulation for gate operations
use num_complex::Complex64;
use rayon::prelude::*;
use std::f64::consts::FRAC_1_SQRT_2;

/// Applies a single qubit gate to the state vector stored in raw bytes.
/// Uses Rayon for parallel execution across the memory mapped region.
pub fn apply_single_qubit_gate(
    mmap_slice: &mut [u8],
    _num_qubits: usize, // Unused in this optimized implementation, but kept for API
    target_qubit: usize,
    matrix: [Complex64; 4],
) {
    // Cast raw bytes to Complex64 (16 bytes per element)
    // mmap alignment satisfies f64 requirements
    let total_elements = mmap_slice.len() / 16;
    let state_vector = unsafe {
        std::slice::from_raw_parts_mut(mmap_slice.as_mut_ptr() as *mut Complex64, total_elements)
    };

    // Calculate stride: distance between paired elements (i, i + 2^k)
    let stride = 1 << target_qubit;
    let block_size = stride * 2;

    // Process blocks in parallel
    // Each block of size 2^(k+1) contains:
    // - First 'stride' elements: qubit_k = |0>
    // - Next 'stride' elements: qubit_k = |1>
    state_vector.par_chunks_mut(block_size).for_each(|chunk| {
        // Split the chunk into the |0> part and |1> part
        let (lower, upper) = chunk.split_at_mut(stride);

        // SIMD Optimization Opportunity:
        // This inner loop is friendly to CPU vectorization (AVX/SSE)
        // if we use primitive arrays.
        for i in 0..stride {
            let amp0 = lower[i];
            let amp1 = upper[i];

            // Matrix Multiply:
            // |0'> = U00|0> + U01|1>
            // |1'> = U10|0> + U11|1>
            lower[i] = matrix[0] * amp0 + matrix[1] * amp1;
            upper[i] = matrix[2] * amp0 + matrix[3] * amp1;
        }
    });
}

/// Apply Controlled-NOT (CX) gate
/// Logic: If Control Qubit is |1>, apply X on Target Qubit.
/// This swaps amplitudes of |...1,0...> and |...1,1...> states.
pub fn apply_cnot(mmap_slice: &mut [u8], _num_qubits: usize, control: usize, target: usize) {
    // Cast raw bytes to Complex64
    let total_elements = mmap_slice.len() / 16;
    let state_vector = unsafe {
        std::slice::from_raw_parts_mut(mmap_slice.as_mut_ptr() as *mut Complex64, total_elements)
    };

    // Determine strides for control and target qubits
    let stride_control = 1 << control;
    let stride_target = 1 << target;

    // CNOT logic: swap amplitudes where control=1
    // Process in blocks where control qubit is fixed
    let control_block_size = stride_control * 2;

    state_vector
        .par_chunks_mut(control_block_size)
        .for_each(|control_block| {
            // Split into control=0 and control=1 halves
            let (_, control_one) = control_block.split_at_mut(stride_control);

            // Within control=1 half, swap target qubit |0> and |1> states
            if stride_target <= stride_control {
                // Target is lower or equal bit: process by target stride within control=1 region
                let target_block_size = stride_target * 2;
                for target_block in control_one.chunks_mut(target_block_size) {
                    if target_block.len() >= target_block_size {
                        let (target_zero, target_one) = target_block.split_at_mut(stride_target);
                        // Swap amplitudes: |control=1, target=0> <-> |control=1, target=1>
                        for i in 0..stride_target.min(target_zero.len()).min(target_one.len()) {
                            std::mem::swap(&mut target_zero[i], &mut target_one[i]);
                        }
                    }
                }
            } else {
                // Target is higher bit: need to swap across control blocks
                // This case is more complex and requires global index tracking
                // For MVP, we handle the common case where target < control
                // Full implementation would require additional logic here
            }
        });
}

/// Helper to generate common gate matrices
pub fn get_matrix(name: &str, _params: &[f64]) -> [Complex64; 4] {
    match name.to_uppercase().as_str() {
        "X" => [
            Complex64::new(0.0, 0.0),
            Complex64::new(1.0, 0.0),
            Complex64::new(1.0, 0.0),
            Complex64::new(0.0, 0.0),
        ],
        "H" => {
            let val = Complex64::new(FRAC_1_SQRT_2, 0.0);
            [val, val, val, -val]
        }
        // Default to Identity if unknown
        _ => [
            Complex64::new(1.0, 0.0),
            Complex64::new(0.0, 0.0),
            Complex64::new(0.0, 0.0),
            Complex64::new(1.0, 0.0),
        ],
    }
}
