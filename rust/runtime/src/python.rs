use pyo3::{exceptions::PyRuntimeError, prelude::*};

use crate::{ExecutionPlan, Runtime, run_batch_from_slice};

fn runtime_error(error: anyhow::Error) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

#[pyfunction(signature = (plan_json, seed=0, until=None))]
fn run_plan_json(
    py: Python<'_>,
    plan_json: String,
    seed: u64,
    until: Option<i64>,
) -> PyResult<String> {
    py.detach(move || {
        let (plan, raw) = ExecutionPlan::from_slice(plan_json.as_bytes())?;
        let fingerprint = ExecutionPlan::fingerprint(&raw)?;
        let result = Runtime::new(plan, fingerprint, seed)?.run(until)?;
        Ok(serde_json::to_string(&result)?)
    })
    .map_err(runtime_error)
}

#[pyfunction(signature = (plan_json, seeds, worker_threads=None, until=None))]
fn run_batch_json(
    py: Python<'_>,
    plan_json: String,
    seeds: Vec<u64>,
    worker_threads: Option<usize>,
    until: Option<i64>,
) -> PyResult<String> {
    py.detach(move || {
        let result = run_batch_from_slice(plan_json.as_bytes(), &seeds, worker_threads, until)?;
        Ok(serde_json::to_string(&result)?)
    })
    .map_err(runtime_error)
}

#[pymodule]
fn _runtime(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(run_plan_json, module)?)?;
    module.add_function(wrap_pyfunction!(run_batch_json, module)?)?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
