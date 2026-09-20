use pyo3::{exceptions::PyRuntimeError, prelude::*};

use std::str::FromStr;

use crate::{ExecutionPlan, ObservationLevel, Runtime, run_batch_from_slice_with_observation};

fn runtime_error(error: anyhow::Error) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

#[pyfunction(signature = (plan_json, seed=0, until=None, observation_level="full"))]
fn run_plan_json(
    py: Python<'_>,
    plan_json: String,
    seed: u64,
    until: Option<i64>,
    observation_level: &str,
) -> PyResult<String> {
    let observation_level = ObservationLevel::from_str(observation_level).map_err(runtime_error)?;
    py.detach(move || {
        let (plan, raw) = ExecutionPlan::from_slice(plan_json.as_bytes())?;
        let fingerprint = ExecutionPlan::fingerprint(&raw)?;
        let result = Runtime::new_with_observation(plan, fingerprint, seed, observation_level)?
            .run(until)?;
        Ok(serde_json::to_string(&result)?)
    })
    .map_err(runtime_error)
}

#[pyfunction(signature = (plan_json, seeds, worker_threads=None, until=None, observation_level="full"))]
fn run_batch_json(
    py: Python<'_>,
    plan_json: String,
    seeds: Vec<u64>,
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: &str,
) -> PyResult<String> {
    let observation_level = ObservationLevel::from_str(observation_level).map_err(runtime_error)?;
    py.detach(move || {
        let result = run_batch_from_slice_with_observation(
            plan_json.as_bytes(),
            &seeds,
            worker_threads,
            until,
            observation_level,
        )?;
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
