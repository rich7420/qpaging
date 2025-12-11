// Virtual Memory Manager
use bitvec::prelude::*;
use memmap2::{MmapMut, MmapOptions};
use std::fs::File;
use std::path::Path;

/// page size typically 4KB, usually defined by system but hardcoded for MVP
const PAGE_SIZE: usize = 4096;

/// Manages the huge state vector file and its memory mapping.
/// Implements "Scope Memory" - resources are tied to this struct's lifetime.
pub struct QuantumMemoryManager {
    mapping: MmapMut,
    _file: File, // Keep file handle open
    pub num_qubits: usize,
    pub total_bytes: usize,
    pub resident_bitmap: BitVec, // Tracks which pages are currently in DRAM
}

impl QuantumMemoryManager {
    /// Create a new memory manager backed by a file on NVMe SSD
    pub fn new(num_qubits: usize, filepath: &str) -> std::io::Result<Self> {
        let total_bytes = (1 << num_qubits) * 16; // Complex128 (16 bytes)

        let path = Path::new(filepath);
        let file = File::options()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)?;
        // Pre-allocate disk space (prevent fragmentation)
        file.set_len(total_bytes as u64)?;
        // Create the memory map
        // Safety: We assume we have exclusive access to this file during simulation
        let mmap = unsafe { MmapOptions::new().map_mut(&file)? };
        // Advice OS: We will manage paging ourselves, don't use standard read-ahead
        unsafe {
            libc::madvise(
                mmap.as_ptr() as *mut _,
                total_bytes,
                libc::MADV_RANDOM, // Disable sequential prefetch
            );
        }
        let total_pages = (total_bytes + PAGE_SIZE - 1) / PAGE_SIZE;
        Ok(Self {
            mapping: mmap,
            _file: file,
            num_qubits,
            total_bytes,
            resident_bitmap: bitvec![0; total_pages],
        })
    }

    /// Unsafe access to the raw pointer for computation kernels
    /// The scheduler MUST ensure the relevant pages are resident before calling this.
    pub fn as_mut_slice(&mut self) -> &mut [u8] {
        &mut self.mapping[..]
    }

    /// [New] Expose raw pointer for io_uring operations
    pub fn as_ptr(&self) -> *const u8 {
        self.mapping.as_ptr()
    }

    /// Provide advice to OS to free pages (Eviction)
    pub fn evict_page(&mut self, page_idx: usize) {
        let offset = page_idx * PAGE_SIZE;
        unsafe {
            libc::madvise(
                self.mapping.as_ptr().add(offset) as *mut _,
                PAGE_SIZE,
                libc::MADV_DONTNEED, // Aggressively free RAM
            );
        }
        self.resident_bitmap.set(page_idx, false);
    }
}

impl Drop for QuantumMemoryManager {
    fn drop(&mut self) {
        // Ensure data hits the disk before we close
        let _ = self.mapping.flush();
    }
}
