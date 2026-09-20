use std::{
    fs,
    path::PathBuf,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Result, bail};
use clap::Parser;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{ExecutionPlan, ObservationLevel, RunResult, Runtime};

mod benchmark_support;

use benchmark_support::{BuildIdentity, build_identity};

#[derive(Parser)]
#[command(about = "Interleaved full/summary observation benchmark")]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "0")]
    seeds: String,
    #[arg(long, default_value_t = 5)]
    repeats: usize,
    #[arg(long, value_name = "PATH")]
    source_diff: Option<PathBuf>,
    #[arg(long, value_name = "PATH")]
    host_manifest: Option<PathBuf>,
}

#[derive(Serialize)]
struct RunRecord {
    repeat: usize,
    seed: u64,
    order: usize,
    observation_level: ObservationLevel,
    execution_ns: u64,
    result_bytes: usize,
    trace_events: usize,
    result_sha256: String,
    sample_requests_sha256: String,
    trace_sha256: String,
    metrics_sha256: String,
    terminal_state_sha256: String,
    result_time: i64,
    result_stop_reason: String,
    result_plan_fingerprint: String,
    result_seed: u64,
}

#[derive(Serialize)]
struct BenchmarkReport {
    schema_version: &'static str,
    generated_at_unix_seconds: u64,
    build: BuildIdentity,
    plan_path: String,
    plan_bytes: usize,
    plan_file_sha256: String,
    plan_fingerprint: String,
    semantic_profile: String,
    work_policy: String,
    rng_profile: String,
    seeds: Vec<u64>,
    repeats: usize,
    records: Vec<RunRecord>,
}

fn digest<T: Serialize>(value: &T) -> Result<String> {
    Ok(format!("{:x}", Sha256::digest(serde_json::to_vec(value)?)))
}

fn run_one(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seed: u64,
    observation_level: ObservationLevel,
    repeat: usize,
    order: usize,
) -> Result<(RunRecord, RunResult)> {
    let runtime =
        Runtime::from_shared_with_observation(plan, fingerprint, seed, observation_level)?;
    let started = Instant::now();
    let result = runtime.run(None)?;
    let execution_ns = started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX);
    let record = RunRecord {
        repeat,
        seed,
        order,
        observation_level,
        execution_ns,
        result_bytes: serde_json::to_vec(&result)?.len(),
        trace_events: result.trace.len(),
        result_sha256: digest(&result)?,
        sample_requests_sha256: digest(&result.sample_requests)?,
        trace_sha256: digest(&result.trace)?,
        metrics_sha256: digest(&result.metrics)?,
        terminal_state_sha256: digest(&result.terminal_state)?,
        result_time: result.time,
        result_stop_reason: result.stop_reason.clone(),
        result_plan_fingerprint: result.plan_fingerprint.clone(),
        result_seed: result.seed,
    };
    Ok((record, result))
}

fn main() -> Result<()> {
    let args = Args::parse();
    if args.repeats == 0 {
        bail!("repeats must be greater than zero");
    }
    let seeds = args
        .seeds
        .split(',')
        .map(|item| item.trim().parse::<u64>())
        .collect::<std::result::Result<Vec<_>, _>>()?;
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }
    let bytes = fs::read(&args.plan)?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let semantic_profile = plan.semantic_profile.clone();
    let work_policy = plan.work_policy.clone();
    let rng_profile = plan.rng_profile.clone();
    let plan = Arc::new(plan);
    let mut records = Vec::with_capacity(seeds.len() * args.repeats * 2);

    for &seed in &seeds {
        for repeat in 0..args.repeats {
            let levels = if repeat % 2 == 0 {
                [ObservationLevel::Full, ObservationLevel::Summary]
            } else {
                [ObservationLevel::Summary, ObservationLevel::Full]
            };
            let mut pair = Vec::with_capacity(2);
            for (order, observation_level) in levels.into_iter().enumerate() {
                let (record, result) = run_one(
                    plan.clone(),
                    fingerprint.clone(),
                    seed,
                    observation_level,
                    repeat,
                    order,
                )?;
                if observation_level == ObservationLevel::Summary && !result.trace.is_empty() {
                    bail!("summary result materialized a trace for seed {seed}");
                }
                records.push(record);
                pair.push(result);
            }
            if pair[0].plan_fingerprint != pair[1].plan_fingerprint
                || pair[0].seed != pair[1].seed
                || pair[0].sample_requests != pair[1].sample_requests
                || pair[0].metrics != pair[1].metrics
                || pair[0].terminal_state != pair[1].terminal_state
                || pair[0].time != pair[1].time
                || pair[0].stop_reason != pair[1].stop_reason
            {
                bail!("observation level changed seed {seed} business or RNG result");
            }
        }
    }

    let report = BenchmarkReport {
        schema_version: "observation-isolation-benchmark/v2",
        generated_at_unix_seconds: SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs(),
        build: build_identity(
            "rust/runtime/src/bin/observation_benchmark.rs",
            include_bytes!("observation_benchmark.rs"),
            args.source_diff.as_deref(),
            args.host_manifest.as_deref(),
        )?,
        plan_path: args.plan.display().to_string(),
        plan_bytes: bytes.len(),
        plan_file_sha256: format!("{:x}", Sha256::digest(&bytes)),
        plan_fingerprint: fingerprint,
        semantic_profile,
        work_policy,
        rng_profile,
        seeds,
        repeats: args.repeats,
        records,
    };
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&report)?)?;
    println!("{}", args.output.display());
    Ok(())
}
