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
    // 1. Safety Cast: Treat raw bytes as Complex64 (16 bytes)
    // We assume the mmap is aligned to page boundaries, which satisfies f64 alignment.
    let total_elements = mmap_slice.len() / 16;
    let state_vector = unsafe {
        std::slice::from_raw_parts_mut(
            mmap_slice.as_mut_ptr() as *mut Complex64,
            total_elements,
        )
    };

    // 2. Determine Stride
    // Stride is the distance between pair elements (i, i + 2^k)
    let stride = 1 << target_qubit;
    let block_size = stride * 2;

    // 3. Parallel Execution Logic
    //
    // The state vector structure repeats every 2^(k+1) elements (block_size).
    // Inside each block:
    // - The first 'stride' elements correspond to qubit_k = |0>
    // - The next 'stride' elements correspond to qubit_k = |1>
    //
    // We use Rayon to process these blocks in parallel.
    state_vector
        .par_chunks_mut(block_size)
        .for_each(|chunk| {
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
        },
        // Default to Identity if unknown
        _ => [
            Complex64::new(1.0, 0.0),
            Complex64::new(0.0, 0.0),
            Complex64::new(0.0, 0.0),
            Complex64::new(1.0, 0.0),
        ],
    }
}
