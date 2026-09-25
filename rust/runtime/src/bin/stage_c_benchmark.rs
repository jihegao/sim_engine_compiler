use std::{
    fs,
    path::{Path, PathBuf},
    str::FromStr,
    sync::Arc,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use clap::Parser;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{BatchResult, ExecutionPlan, ObservationLevel, Runtime, run_batch_with_observation};

#[derive(Parser)]
#[command(about = "Segmented Stage C benchmark for the independent Rust runtime")]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "0,1,7")]
    seeds: String,
    #[arg(long, default_value_t = 1)]
    worker_threads: usize,
    #[arg(long, default_value_t = 1)]
    warmups: usize,
    #[arg(long, default_value_t = 3)]
    repeats: usize,
    #[arg(long)]
    until: Option<i64>,
    #[arg(long, default_value = "full")]
    observation_level: String,
}

#[derive(Serialize)]
struct PhaseTimings {
    plan_read_ns: u64,
    plan_parse_validate_ns: u64,
    fingerprint_ns: u64,
    run_state_initialization_ns: u64,
    single_sample_execution_ns: u64,
    single_sample_serialization_ns: u64,
    batch_execution_ns: u64,
    batch_serialization_ns: u64,
    batch_write_ns: u64,
    end_to_end_batch_ns: u64,
}

#[derive(Serialize)]
struct RepeatRecord {
    repeat: usize,
    phases: PhaseTimings,
    single_result_bytes: usize,
    batch_result_bytes: usize,
    batch_result_sha256: String,
    samples_sha256: String,
    sample_indexes: Vec<usize>,
    seeds: Vec<u64>,
}

#[derive(Serialize)]
struct BenchmarkReport {
    schema_version: &'static str,
    generated_at_unix_seconds: u64,
    runtime_version: &'static str,
    rustc: String,
    operating_system: &'static str,
    architecture: &'static str,
    available_parallelism: usize,
    plan_path: String,
    plan_bytes: usize,
    plan_fingerprint: String,
    semantic_profile: String,
    work_policy: String,
    rng_profile: String,
    seeds: Vec<u64>,
    worker_threads: usize,
    warmups: usize,
    repeats: usize,
    until: Option<i64>,
    observation_level: ObservationLevel,
    records: Vec<RepeatRecord>,
}

fn elapsed_ns(start: Instant) -> u64 {
    start.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
}

fn parse_seeds(raw: &str) -> Result<Vec<u64>> {
    let seeds = raw
        .split(',')
        .map(|item| item.trim().parse::<u64>())
        .collect::<std::result::Result<Vec<_>, _>>()?;
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }
    Ok(seeds)
}

fn rustc_version() -> String {
    std::process::Command::new("rustc")
        .arg("--version")
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_owned())
        .unwrap_or_else(|| "unavailable".into())
}

fn write_payload(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, bytes)?;
    Ok(())
}

fn execute_batch(
    plan: Arc<ExecutionPlan>,
    fingerprint: String,
    seeds: &[u64],
    worker_threads: usize,
    until: Option<i64>,
    observation_level: ObservationLevel,
) -> Result<BatchResult> {
    run_batch_with_observation(plan, fingerprint, seeds, Some(worker_threads), until, observation_level)
}

fn main() -> Result<()> {
    let args = Args::parse();
    let observation_level = ObservationLevel::from_str(&args.observation_level)?;
    if args.worker_threads == 0 || args.repeats == 0 {
        bail!("worker_threads and repeats must be greater than zero");
    }
    let seeds = parse_seeds(&args.seeds)?;
    let effective_worker_threads = args.worker_threads.min(seeds.len()).max(1);
    let initial_bytes = fs::read(&args.plan)?;
    let (initial_plan, initial_raw) = ExecutionPlan::from_slice(&initial_bytes)?;
    let initial_fingerprint = ExecutionPlan::fingerprint(&initial_raw)?;
    let initial_plan = Arc::new(initial_plan);

    for _ in 0..args.warmups {
        let _ = execute_batch(
            initial_plan.clone(),
            initial_fingerprint.clone(),
            &seeds,
            args.worker_threads,
            args.until,
            observation_level,
        )?;
    }

    let scratch = args.output.with_extension("payload.tmp");
    let mut records = Vec::with_capacity(args.repeats);
    for repeat in 0..args.repeats {
        let started = Instant::now();
        let bytes = fs::read(&args.plan)?;
        let plan_read_ns = elapsed_ns(started);

        let started = Instant::now();
        let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
        let plan_parse_validate_ns = elapsed_ns(started);

        let started = Instant::now();
        let fingerprint = ExecutionPlan::fingerprint(&raw)?;
        let fingerprint_ns = elapsed_ns(started);
        let plan = Arc::new(plan);

        let started = Instant::now();
        let runtime = Runtime::from_shared_with_observation(plan.clone(), fingerprint.clone(), seeds[0], observation_level)?;
        let run_state_initialization_ns = elapsed_ns(started);

        let started = Instant::now();
        let single_result = runtime.run(args.until)?;
        let single_sample_execution_ns = elapsed_ns(started);

        let started = Instant::now();
        let single_json = serde_json::to_vec(&single_result)?;
        let single_sample_serialization_ns = elapsed_ns(started);

        let started = Instant::now();
        let batch = execute_batch(plan, fingerprint, &seeds, args.worker_threads, args.until, observation_level)?;
        let batch_execution_ns = elapsed_ns(started);

        let started = Instant::now();
        let batch_json = serde_json::to_vec(&batch)?;
        let batch_serialization_ns = elapsed_ns(started);

        let started = Instant::now();
        write_payload(&scratch, &batch_json)?;
        let batch_write_ns = elapsed_ns(started);

        let started = Instant::now();
        let end_to_end_bytes = fs::read(&args.plan)?;
        let (end_to_end_plan, end_to_end_raw) = ExecutionPlan::from_slice(&end_to_end_bytes)?;
        let end_to_end_fingerprint = ExecutionPlan::fingerprint(&end_to_end_raw)?;
        let end_to_end_batch = execute_batch(
            Arc::new(end_to_end_plan),
            end_to_end_fingerprint,
            &seeds,
            args.worker_threads,
            args.until,
            observation_level,
        )?;
        let end_to_end_json = serde_json::to_vec(&end_to_end_batch)?;
        write_payload(&scratch, &end_to_end_json)?;
        let end_to_end_batch_ns = elapsed_ns(started);

        records.push(RepeatRecord {
            repeat,
            phases: PhaseTimings {
                plan_read_ns,
                plan_parse_validate_ns,
                fingerprint_ns,
                run_state_initialization_ns,
                single_sample_execution_ns,
                single_sample_serialization_ns,
                batch_execution_ns,
                batch_serialization_ns,
                batch_write_ns,
                end_to_end_batch_ns,
            },
            single_result_bytes: single_json.len(),
            batch_result_bytes: batch_json.len(),
            batch_result_sha256: format!("{:x}", Sha256::digest(&batch_json)),
            samples_sha256: format!("{:x}", Sha256::digest(serde_json::to_vec(&batch.samples)?)),
            sample_indexes: batch
                .samples
                .iter()
                .map(|sample| sample.sample_index)
                .collect(),
            seeds: batch.samples.iter().map(|sample| sample.seed).collect(),
        });
    }
    let _ = fs::remove_file(&scratch);

    let report = BenchmarkReport {
        schema_version: "stage-c-segmented-benchmark/v1",
        generated_at_unix_seconds: SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs(),
        runtime_version: env!("CARGO_PKG_VERSION"),
        rustc: rustc_version(),
        operating_system: std::env::consts::OS,
        architecture: std::env::consts::ARCH,
        available_parallelism: std::thread::available_parallelism()
            .map(|value| value.get())
            .unwrap_or(1),
        plan_path: args.plan.display().to_string(),
        plan_bytes: initial_bytes.len(),
        plan_fingerprint: initial_fingerprint,
        semantic_profile: initial_plan.semantic_profile.clone(),
        work_policy: initial_plan.work_policy.clone(),
        rng_profile: initial_plan.rng_profile.clone(),
        seeds,
        worker_threads: effective_worker_threads,
        warmups: args.warmups,
        repeats: args.repeats,
        until: args.until,
        observation_level,
        records,
    };
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create benchmark directory {}", parent.display()))?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&report)?)?;
    println!("{}", args.output.display());
    Ok(())
}
