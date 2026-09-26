use std::{collections::HashSet, num::NonZeroUsize, sync::Arc, thread, time::Instant};

use anyhow::{Result, bail};
use rayon::prelude::*;
use serde::Serialize;

use crate::runtime::PreparedBatchPlan;
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

#[derive(Clone, Debug)]
pub struct IndexedSampleRequest {
    pub sample_index: usize,
    pub seed: u64,
}

#[derive(Clone, Debug)]
pub struct PlanBatchGroup {
    pub group_index: usize,
    pub plan: Arc<ExecutionPlan>,
    pub plan_fingerprint: String,
    pub samples: Vec<IndexedSampleRequest>,
}

#[derive(Debug, Serialize)]
pub struct IndexedBatchSampleResult {
    pub group_index: usize,
    pub sample_index: usize,
    pub seed: u64,
    pub result: RunResult,
}

#[derive(Debug, Serialize)]
pub struct IndexedBatchSampleFailure {
    pub group_index: usize,
    pub sample_index: usize,
    pub seed: u64,
    pub error: String,
}

#[derive(Debug, Serialize)]
pub struct IndexedPlanBatchResult {
    pub sample_count: usize,
    pub worker_threads: usize,
    pub prepare_ns: u64,
    pub execute_ns: u64,
    pub samples: Vec<IndexedBatchSampleResult>,
    pub failed_samples: Vec<IndexedBatchSampleFailure>,
}

fn elapsed_ns(started: Instant) -> u64 {
    started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
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
    let prepared = Arc::new(PreparedBatchPlan::from_slice(plan_bytes)?);
    run_prepared_batch(
        prepared,
        seeds,
        worker_threads,
        until,
        observation_level,
        false,
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
    run_batch_with_dispatch(
        plan,
        fingerprint,
        seeds,
        worker_threads,
        until,
        observation_level,
        false,
    )
}

pub fn run_batch_with_dispatch(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: ObservationLevel,
    dependency_dispatch: bool,
) -> Result<BatchResult> {
    if seeds.is_empty() {
        bail!("batch request must contain at least one seed");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }
    let prepared = Arc::new(PreparedBatchPlan::from_plan(plan, fingerprint)?);
    run_prepared_batch(
        prepared,
        seeds,
        worker_threads,
        until,
        observation_level,
        dependency_dispatch,
    )
}

/// Run another batch against the same validated, immutable prepared Plan.
pub fn run_prepared_batch(
    prepared: Arc<PreparedBatchPlan>,
    seeds: &[u64],
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: ObservationLevel,
    dependency_dispatch: bool,
) -> Result<BatchResult> {
    if seeds.is_empty() {
        bail!("batch request must contain at least one seed");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }

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
                let result = Runtime::from_prepared_with_observation(
                    prepared.clone(),
                    *seed,
                    observation_level,
                )?
                .with_dependency_dispatch(dependency_dispatch)?
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
        plan_fingerprint: prepared.fingerprint().to_owned(),
        sample_count: samples.len(),
        worker_threads,
        until,
        samples,
    })
}

/// Execute samples from multiple immutable plans in one bounded Rayon pool.
///
/// Each group prepares its plan once and shares that read-only layout among
/// all samples in the group. Mutable runtime state remains isolated per
/// sample. Results and failures are sorted by the caller-provided stable
/// `sample_index`, independent of scheduling and completion order.
pub fn run_indexed_plan_batch_with_observation(
    groups: Vec<PlanBatchGroup>,
    worker_threads: Option<usize>,
    until: Option<i64>,
    observation_level: ObservationLevel,
) -> Result<IndexedPlanBatchResult> {
    if groups.is_empty() {
        bail!("indexed batch request must contain at least one plan group");
    }
    if worker_threads == Some(0) {
        bail!("worker_threads must be greater than zero");
    }

    let sample_count = groups
        .iter()
        .map(|group| group.samples.len())
        .sum::<usize>();
    if sample_count == 0 {
        bail!("indexed batch request must contain at least one sample");
    }
    let mut sample_indexes = HashSet::with_capacity(sample_count);
    for group in &groups {
        if group.samples.is_empty() {
            bail!("plan group {} contains no samples", group.group_index);
        }
        for sample in &group.samples {
            if !sample_indexes.insert(sample.sample_index) {
                bail!("duplicate sample_index {}", sample.sample_index);
            }
        }
    }

    struct PreparedGroup {
        group_index: usize,
        prepared: Arc<PreparedBatchPlan>,
        samples: Vec<IndexedSampleRequest>,
    }

    let prepare_started = Instant::now();
    let prepared_groups = groups
        .into_iter()
        .map(|group| -> Result<PreparedGroup> {
            Ok(PreparedGroup {
                group_index: group.group_index,
                prepared: Arc::new(PreparedBatchPlan::from_plan(
                    group.plan,
                    group.plan_fingerprint,
                )?),
                samples: group.samples,
            })
        })
        .collect::<Result<Vec<_>>>()?;
    let prepare_ns = elapsed_ns(prepare_started);

    struct WorkItem {
        group_index: usize,
        prepared: Arc<PreparedBatchPlan>,
        sample: IndexedSampleRequest,
    }

    let work = prepared_groups
        .into_iter()
        .flat_map(|group| {
            group.samples.into_iter().map(move |sample| WorkItem {
                group_index: group.group_index,
                prepared: group.prepared.clone(),
                sample,
            })
        })
        .collect::<Vec<_>>();

    let available = thread::available_parallelism()
        .map(NonZeroUsize::get)
        .unwrap_or(1);
    let worker_threads = worker_threads.unwrap_or(available).min(sample_count).max(1);
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(worker_threads)
        .thread_name(|index| format!("sim-indexed-sample-{index}"))
        .build()?;

    enum Outcome {
        Success(IndexedBatchSampleResult),
        Failure(IndexedBatchSampleFailure),
    }

    let execute_started = Instant::now();
    let outcomes = pool.install(|| {
        work.par_iter()
            .map(|item| {
                let run = Runtime::from_prepared_with_observation(
                    item.prepared.clone(),
                    item.sample.seed,
                    observation_level,
                )
                .and_then(|runtime| runtime.run(until));
                match run {
                    Ok(result) => Outcome::Success(IndexedBatchSampleResult {
                        group_index: item.group_index,
                        sample_index: item.sample.sample_index,
                        seed: item.sample.seed,
                        result,
                    }),
                    Err(error) => Outcome::Failure(IndexedBatchSampleFailure {
                        group_index: item.group_index,
                        sample_index: item.sample.sample_index,
                        seed: item.sample.seed,
                        error: format!("{error:#}"),
                    }),
                }
            })
            .collect::<Vec<_>>()
    });
    let execute_ns = elapsed_ns(execute_started);

    let mut samples = Vec::new();
    let mut failed_samples = Vec::new();
    for outcome in outcomes {
        match outcome {
            Outcome::Success(sample) => samples.push(sample),
            Outcome::Failure(failure) => failed_samples.push(failure),
        }
    }
    samples.sort_by_key(|sample| sample.sample_index);
    failed_samples.sort_by_key(|sample| sample.sample_index);

    Ok(IndexedPlanBatchResult {
        sample_count,
        worker_threads,
        prepare_ns,
        execute_ns,
        samples,
        failed_samples,
    })
}

#[cfg(test)]
mod prepared_batch_tests {
    use super::*;

    const INDEXED_PLAN: &[u8] = include_bytes!(
        "../../../benchmarks/dependency_dispatch/results/macos-arm64-20260925/synthetic-capacity-16/event-time-v2/indexed-plan.json"
    );

    #[test]
    fn reused_prepared_plan_preserves_results_and_duplicate_seed_order() {
        let prepared = Arc::new(PreparedBatchPlan::from_slice(INDEXED_PLAN).unwrap());
        let seeds = [7, 7, 0, 1];
        for observation in [ObservationLevel::Full, ObservationLevel::Summary] {
            for dependency_dispatch in [false, true] {
                let serial = run_prepared_batch(
                    prepared.clone(),
                    &seeds,
                    Some(1),
                    None,
                    observation,
                    dependency_dispatch,
                )
                .unwrap();
                let parallel = run_prepared_batch(
                    prepared.clone(),
                    &seeds,
                    Some(4),
                    None,
                    observation,
                    dependency_dispatch,
                )
                .unwrap();
                let old_entry = run_batch_with_dispatch(
                    Arc::new(ExecutionPlan::from_slice(INDEXED_PLAN).unwrap().0),
                    prepared.fingerprint().to_owned(),
                    &seeds,
                    Some(4),
                    None,
                    observation,
                    dependency_dispatch,
                )
                .unwrap();
                assert_eq!(
                    serde_json::to_value(&serial.samples).unwrap(),
                    serde_json::to_value(&parallel.samples).unwrap()
                );
                assert_eq!(
                    serde_json::to_value(&parallel.samples).unwrap(),
                    serde_json::to_value(&old_entry.samples).unwrap()
                );
                assert_eq!(
                    parallel
                        .samples
                        .iter()
                        .map(|sample| sample.sample_index)
                        .collect::<Vec<_>>(),
                    vec![0, 1, 2, 3]
                );
            }
        }
    }

    #[test]
    fn prepared_entry_rejects_invalid_plan_and_index_before_running() {
        let mut raw: serde_json::Value = serde_json::from_slice(INDEXED_PLAN).unwrap();
        raw["resource_dispatch_index"]["checksum"] = "invalid".into();
        let corrupt_index = serde_json::to_vec(&raw).unwrap();
        assert!(PreparedBatchPlan::from_slice(&corrupt_index).is_err());
        let plan: ExecutionPlan = serde_json::from_slice(&corrupt_index).unwrap();
        assert!(PreparedBatchPlan::from_plan(Arc::new(plan), "unused".into()).is_err());

        let mut raw: serde_json::Value = serde_json::from_slice(INDEXED_PLAN).unwrap();
        raw["activities"][0]["resource_node_index"] = usize::MAX.into();
        raw.as_object_mut()
            .unwrap()
            .remove("resource_dispatch_index");
        assert!(PreparedBatchPlan::from_slice(&serde_json::to_vec(&raw).unwrap()).is_err());
    }
}
