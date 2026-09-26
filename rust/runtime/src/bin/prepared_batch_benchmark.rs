use std::{fs, path::PathBuf, str::FromStr, sync::Arc, time::Instant};

use anyhow::{Result, bail};
use clap::Parser;
use serde::Serialize;
use sha2::{Digest, Sha256};
use sim_engine_runtime::{
    ExecutionPlan, ObservationLevel, PreparedBatchPlan, run_batch_with_dispatch, run_prepared_batch,
};

#[derive(Parser)]
#[command(about = "Compare repeated public-batch calls with a reusable prepared Plan")]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value = "0,1,7,7")]
    seeds: String,
    #[arg(long, default_value_t = 1)]
    worker_threads: usize,
    #[arg(long, default_value_t = 1)]
    warmups: usize,
    #[arg(long, default_value_t = 6)]
    repeats: usize,
    #[arg(long, default_value = "summary")]
    observation_level: String,
    #[arg(long)]
    dependency_dispatch: bool,
}

#[derive(Serialize)]
struct Row {
    repeat: usize,
    mode: &'static str,
    run_ns: u64,
    serialize_ns: u64,
    sample_sha256: String,
    result_bytes: usize,
}

#[derive(Serialize)]
struct Report {
    schema_version: &'static str,
    plan_sha256: String,
    plan_fingerprint: String,
    seeds: Vec<u64>,
    worker_threads: usize,
    observation_level: ObservationLevel,
    dependency_dispatch: bool,
    preparation_ns: u64,
    rows: Vec<Row>,
}

fn elapsed_ns(started: Instant) -> u64 {
    started.elapsed().as_nanos().try_into().unwrap_or(u64::MAX)
}

fn main() -> Result<()> {
    let args = Args::parse();
    if args.worker_threads == 0 || args.repeats == 0 {
        bail!("worker_threads and repeats must be positive");
    }
    let seeds = args
        .seeds
        .split(',')
        .map(|seed| seed.parse::<u64>())
        .collect::<std::result::Result<Vec<_>, _>>()?;
    if seeds.is_empty() {
        bail!("at least one seed is required");
    }
    let observation_level = ObservationLevel::from_str(&args.observation_level)?;
    let bytes = fs::read(&args.plan)?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let plan = Arc::new(plan);
    let started = Instant::now();
    let prepared = Arc::new(PreparedBatchPlan::from_plan(
        plan.clone(),
        fingerprint.clone(),
    )?);
    let preparation_ns = elapsed_ns(started);

    let run = |mode| {
        if mode == "prepared" {
            run_prepared_batch(
                prepared.clone(),
                &seeds,
                Some(args.worker_threads),
                None,
                observation_level,
                args.dependency_dispatch,
            )
        } else {
            run_batch_with_dispatch(
                plan.clone(),
                fingerprint.clone(),
                &seeds,
                Some(args.worker_threads),
                None,
                observation_level,
                args.dependency_dispatch,
            )
        }
    };
    for _ in 0..args.warmups {
        run("public")?;
        run("prepared")?;
    }
    let mut rows = Vec::new();
    for repeat in 0..args.repeats {
        let order = if repeat % 2 == 0 {
            ["public", "prepared"]
        } else {
            ["prepared", "public"]
        };
        let mut expected = None;
        for mode in order {
            let started = Instant::now();
            let result = run(mode)?;
            let run_ns = elapsed_ns(started);
            let started = Instant::now();
            let sample_json = serde_json::to_vec(&result.samples)?;
            let result_bytes = serde_json::to_vec(&result)?.len();
            let serialize_ns = elapsed_ns(started);
            let sample_sha256 = format!("{:x}", Sha256::digest(sample_json));
            if let Some(expected) = &expected {
                assert_eq!(expected, &sample_sha256, "public/prepared result mismatch");
            } else {
                expected = Some(sample_sha256.clone());
            }
            rows.push(Row {
                repeat,
                mode,
                run_ns,
                serialize_ns,
                sample_sha256,
                result_bytes,
            });
        }
    }
    let report = Report {
        schema_version: "prepared-batch-benchmark/v1",
        plan_sha256: format!("{:x}", Sha256::digest(&bytes)),
        plan_fingerprint: fingerprint,
        seeds,
        worker_threads: args.worker_threads,
        observation_level,
        dependency_dispatch: args.dependency_dispatch,
        preparation_ns,
        rows,
    };
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&report)?)?;
    Ok(())
}
