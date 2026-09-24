use std::{fs, path::PathBuf, str::FromStr, time::Instant};

use anyhow::Result;
use clap::Parser;
use sim_engine_runtime::{
    ExecutionPlan, ObservationLevel, Runtime, decode_plan_cache, is_plan_cache,
    run_batch_with_observation,
};

#[derive(Parser)]
#[command(about = "Execute an aircraft-support Execution Plan with the independent Rust runtime")]
#[command(version)]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, conflicts_with = "seeds")]
    seed: Option<u64>,
    #[arg(long, value_name = "SEED,...", conflicts_with = "seed")]
    seeds: Option<String>,
    #[arg(long, requires = "seeds")]
    worker_threads: Option<usize>,
    #[arg(long)]
    until: Option<i64>,
    #[arg(long, default_value = "full")]
    observation_level: String,
    #[arg(long, conflicts_with = "seeds")]
    profile_output: Option<PathBuf>,
}

fn main() -> Result<()> {
    let process_started = Instant::now();
    let args = Args::parse();
    let load_started = Instant::now();
    let bytes = fs::read(&args.plan)?;
    let (plan, fingerprint) = if is_plan_cache(&bytes) {
        let cached = decode_plan_cache(&bytes, None, None, None)?;
        (cached.plan, cached.plan_fingerprint)
    } else {
        let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
        let fingerprint = ExecutionPlan::fingerprint(&raw)?;
        (plan, fingerprint)
    };
    let plan_load_ns = load_started.elapsed().as_nanos();
    let observation_level = ObservationLevel::from_str(&args.observation_level)?;
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    if let Some(raw_seeds) = args.seeds {
        let seeds = raw_seeds
            .split(',')
            .map(|item| item.trim().parse::<u64>())
            .collect::<std::result::Result<Vec<_>, _>>()?;
        let result = run_batch_with_observation(
            std::sync::Arc::new(plan),
            fingerprint,
            &seeds,
            args.worker_threads,
            args.until,
            observation_level,
        )?;
        fs::write(&args.output, serde_json::to_vec_pretty(&result)?)?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "plan_fingerprint": result.plan_fingerprint,
                "sample_count": result.sample_count,
                "worker_threads": result.worker_threads,
                "sample_indexes": result.samples.iter().map(|item| item.sample_index).collect::<Vec<_>>(),
                "seeds": result.samples.iter().map(|item| item.seed).collect::<Vec<_>>(),
            }))?
        );
    } else {
        let init_started = Instant::now();
        let runtime = Runtime::new_with_observation(
            plan,
            fingerprint,
            args.seed.unwrap_or(0),
            observation_level,
        )?;
        let initialization_ns = init_started.elapsed().as_nanos();
        let (result, profile) = if args.profile_output.is_some() {
            let (result, profile) = runtime.run_profiled(args.until)?;
            (result, Some(profile))
        } else {
            (runtime.run(args.until)?, None)
        };
        let write_started = Instant::now();
        fs::write(&args.output, serde_json::to_vec_pretty(&result)?)?;
        let result_write_ns = write_started.elapsed().as_nanos();
        if let (Some(path), Some(profile)) = (args.profile_output.as_ref(), profile) {
            if let Some(parent) = path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::write(
                path,
                serde_json::to_vec_pretty(&serde_json::json!({
                    "plan_load_ns": plan_load_ns,
                    "initialization_ns": initialization_ns,
                    "execution_ns": profile.execution_ns,
                    "result_write_ns": result_write_ns,
                    "process_wall_ns": process_started.elapsed().as_nanos(),
                    "profile": profile,
                }))?,
            )?;
        }
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "plan_fingerprint": result.plan_fingerprint, "time": result.time,
                "stop_reason": result.stop_reason, "events": result.trace.len(),
            }))?
        );
    }
    Ok(())
}
