use std::{num::NonZeroUsize, sync::Arc, thread};

use anyhow::{Result, bail};
use rayon::prelude::*;
use serde::Serialize;

use crate::{ExecutionPlan, RunResult, Runtime};

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
    let (plan, raw) = ExecutionPlan::from_slice(plan_bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    run_batch(Arc::new(plan), fingerprint, seeds, worker_threads, until)
}

pub fn run_batch(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
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
                let result =
                    Runtime::from_shared(plan.clone(), fingerprint.clone(), *seed)?.run(until)?;
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
