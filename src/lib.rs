use pyo3::prelude::*;

use crate::engine::controller::SimulatorController;

mod engine;

/// Python module definition
#[pymodule]
fn qp_sim_core(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Expose the main Controller class to Python
    m.add_class::<SimulatorController>()?;
    Ok(())
}
