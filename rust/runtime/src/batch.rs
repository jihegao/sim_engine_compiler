use std::{num::NonZeroUsize, sync::Arc, thread};

use anyhow::{Result, bail};
use rayon::prelude::*;
use serde::Serialize;

use crate::{ExecutionPlan, ObservationLevel, RunResult, Runtime};

#[derive(Debug, Serialize)]
pub struct BatchSampleResult {
    pub sample_index: usize,
    pub seed: u64,
    pub result: RunResult,
}

#[derive(Debug, Serialize)]
pub struct BatchResult {
    pub plan_fingerprint: String,
    pub sample_count: usize,
    pub worker_threads: usize,
    pub until: Option<i64>,
    pub samples: Vec<BatchSampleResult>,
}

pub fn run_batch_from_slice(
    plan_bytes: &[u8],
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
) -> Result<BatchResult> {
    run_batch_from_slice_with_observation(
        plan_bytes,
        seeds,
        worker_threads,
        until,
        ObservationLevel::Full,
    )
}

pub fn run_batch_from_slice_with_observation(
    plan_bytes: &[u8],
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: ObservationLevel,
) -> Result<BatchResult> {
    let (plan, raw) = ExecutionPlan::from_slice(plan_bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    run_batch_with_observation(
        Arc::new(plan),
        fingerprint,
        seeds,
        worker_threads,
        until,
        observation_level,
    )
}

pub fn run_batch(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
) -> Result<BatchResult> {
    run_batch_with_observation(
        plan,
        fingerprint,
        seeds,
        worker_threads,
        until,
        ObservationLevel::Full,
    )
}

pub fn run_batch_with_observation(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: ObservationLevel,
) -> Result<BatchResult> {
    if seeds.is_empty() {
        bail!("batch request must contain at least one seed");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }
    plan.validate()?;

    let available = thread::available_parallelism()
        .map(NonZeroUsize::get)
        .unwrap_or(1);
    let worker_threads = worker_threads.unwrap_or(available).min(seeds.len()).max(1);
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(worker_threads)
        .thread_name(|index| format!("sim-sample-{index}"))
        .build()?;

    let outcomes: Vec<Result<BatchSampleResult>> = pool.install(|| {
        seeds
            .par_iter()
            .enumerate()
            .map(|(sample_index, seed)| {
                let result = Runtime::from_shared_with_observation(
                    plan.clone(),
                    fingerprint.clone(),
                    *seed,
                    observation_level,
                )?
                .run(until)?;
                Ok(BatchSampleResult {
                    sample_index,
                    seed: *seed,
                    result,
                })
            })
            .collect()
    });
    let mut samples: Vec<_> = outcomes.into_iter().collect::<Result<_>>()?;
    // The output contract is independent of Rayon scheduling and completion order.
    samples.sort_by_key(|sample| sample.sample_index);

    Ok(BatchResult {
        plan_fingerprint: fingerprint,
        sample_count: samples.len(),
        worker_threads,
        until,
        samples,
    })
}
