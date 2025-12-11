// Async I/O Engine with BitVec Support
use bitvec::prelude::*;
use io_uring::{opcode, IoUring};

const PAGE_SIZE: usize = 4096;

pub struct AsyncIoEngine {
    ring: IoUring,
    queue_depth: u32,
}

impl AsyncIoEngine {
    pub fn new(queue_depth: u32) -> std::io::Result<Self> {
        let ring = IoUring::new(queue_depth)?;
        Ok(Self { ring, queue_depth })
    }

    /// The Core Logic of Phase 2: Deterministic Prefetching
    /// Takes a set of required pages (BitVec), coalesces contiguous ranges,
    /// and submits async MADV_WILLNEED requests to the kernel.
    pub fn submit_prefetch(
        &mut self,
        pages: &BitVec,
        base_addr: *const u8,
    ) -> std::io::Result<usize> {
        let mut submitted_count = 0;
        let mut start_idx: Option<usize> = None;
        let mut current_len = 0;

        // 1. Coalescing Algorithm: Find contiguous runs of true bits
        for idx in pages.iter_ones() {
            match start_idx {
                Some(start) => {
                    if idx == start + current_len {
                        // Contiguous: extend current block
                        current_len += 1;
                    } else {
                        // Gap detected: submit previous block and start new one
                        self.submit_madvise_op(base_addr, start, current_len)?;
                        submitted_count += 1;

                        start_idx = Some(idx);
                        current_len = 1;
                    }
                }
                None => {
                    // Start new block
                    start_idx = Some(idx);
                    current_len = 1;
                }
            }
        }

        // Submit the final block if exists
        if let Some(start) = start_idx {
            self.submit_madvise_op(base_addr, start, current_len)?;
            submitted_count += 1;
        }

        // 2. Push to Kernel
        self.ring.submit()?;

        Ok(submitted_count)
    }

    /// Create and push a single io_uring SQE
    fn submit_madvise_op(
        &mut self,
        base_addr: *const u8,
        start_page_idx: usize,
        num_pages: usize,
    ) -> std::io::Result<()> {
        // Calculate memory address range
        let offset = start_page_idx * PAGE_SIZE;
        let length = num_pages * PAGE_SIZE;

        unsafe {
            let addr = base_addr.add(offset);

            // MADV_WILLNEED: Tells OS to read these pages into RAM ASAP
            // Note: io_uring's Madvise opcode takes raw pointer and length
            let op = opcode::Madvise::new(addr as *const _, length as i64, libc::MADV_WILLNEED)
                .build()
                .user_data(start_page_idx as u64); // Track ID

            if self.ring.submission().is_full() {
                // If queue is full, force submit to clear space
                self.ring.submit()?;
            }

            self.ring.submission().push(&op).map_err(|_| {
                std::io::Error::new(std::io::ErrorKind::Other, "Submission queue full")
            })?;
        }
        Ok(())
    }

    /// Poll for completed IO tasks (clean up CQ)
    pub fn reap_completions(&mut self) -> usize {
        let mut completed = 0;
        let mut cq = self.ring.completion();

        // Sync: check what's done without blocking
        // In a real optimized loop, we might want to `cq.wait_for_cqe()` if we are strictly bound by IO
        // But for prefetching, we just want to clean up.
        while let Some(_cqe) = cq.next() {
            // In a robust system, we check cqe.result() for errors
            completed += 1;
        }

        completed
    }
}
