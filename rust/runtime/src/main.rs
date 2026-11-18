use std::{fs, path::PathBuf, str::FromStr, time::Instant};

use anyhow::Result;
use clap::Parser;
use sim_engine_runtime::{
    AbmPlanEnvelope, AbmRandomTape, AbmSampleRequest, ExecutionPlan, ObservationLevel, Runtime,
    decode_plan_cache, is_plan_cache, is_queue_plan, run_abm_batch,
    run_abm_plan_with_random_tape, run_batch_with_dispatch, run_queue_batch_json,
    run_queue_plan_json,
};

#[derive(Parser)]
#[command(about = "Execute an aircraft-support Execution Plan with the independent Rust runtime")]
#[command(version)]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, conflicts_with = "seeds")]
    seed: Option<String>,
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
    #[arg(long)]
    dependency_dispatch: bool,
    #[arg(long, value_name = "PATH", conflicts_with = "seeds")]
    random_tape: Option<PathBuf>,
}

fn main() -> Result<()> {
    let process_started = Instant::now();
    let args = Args::parse();
    let load_started = Instant::now();
    let bytes = fs::read(&args.plan)?;
    if !is_plan_cache(&bytes) {
        let document = serde_json::from_slice::<serde_json::Value>(&bytes)?;
        if document["version"] == sim_engine_runtime::ABM_PLAN_VERSION {
            return run_abm_cli(args, &bytes);
        }
        if is_queue_plan(&document) {
            return run_queue_cli(args, &bytes);
        }
    }
    if args.random_tape.is_some() {
        anyhow::bail!("random tape is only supported for ABM Plans");
    }
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
        let result = run_batch_with_dispatch(
            std::sync::Arc::new(plan),
            fingerprint,
            &seeds,
            args.worker_threads,
            args.until,
            observation_level,
            args.dependency_dispatch,
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
            args.seed.as_deref().unwrap_or("0").parse::<u64>()?,
            observation_level,
        )?
        .with_dependency_dispatch(args.dependency_dispatch)?;
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

fn run_queue_cli(args: Args, bytes: &[u8]) -> Result<()> {
    if args.profile_output.is_some() || args.dependency_dispatch || args.random_tape.is_some() {
        anyhow::bail!(
            "queue plans do not support profile output, dependency dispatch, or random tape"
        );
    }
    let plan_json = std::str::from_utf8(bytes)?;
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    if let Some(raw_seeds) = args.seeds {
        let seeds = raw_seeds
            .split(',')
            .map(|item| item.trim().parse::<u64>())
            .collect::<std::result::Result<Vec<_>, _>>()?;
        let encoded = run_queue_batch_json(
            plan_json,
            &seeds,
            args.worker_threads,
            args.until,
            &args.observation_level,
        )?;
        fs::write(&args.output, &encoded)?;
        let result: serde_json::Value = serde_json::from_str(&encoded)?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "plan_fingerprint": result["plan_fingerprint"],
                "sample_count": result["sample_count"],
                "worker_threads": result["worker_threads"],
            }))?
        );
    } else {
        let seed = args.seed.as_deref().unwrap_or("0").parse::<u64>()?;
        let encoded = run_queue_plan_json(plan_json, seed, 0, args.until, &args.observation_level)?;
        fs::write(&args.output, &encoded)?;
        let result: serde_json::Value = serde_json::from_str(&encoded)?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "plan_fingerprint": result["plan_fingerprint"],
                "time": result["time"],
                "stop_reason": result["stop_reason"],
                "events": result["trace"].as_array().map(|items| items.len()).unwrap_or(0),
            }))?
        );
    }
    Ok(())
}

fn run_abm_cli(args: Args, bytes: &[u8]) -> Result<()> {
    if args.until.is_some()
        || args.profile_output.is_some()
        || args.dependency_dispatch
        || args.observation_level != "full"
    {
        anyhow::bail!(
            "ABM Plan does not support aircraft-only until, profile, dependency-dispatch, or observation options"
        );
    }
    let plan = std::sync::Arc::new(AbmPlanEnvelope::from_slice(bytes)?);
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    if let Some(raw_seeds) = args.seeds {
        let requests = raw_seeds
            .split(',')
            .enumerate()
            .map(|(sample_index, item)| {
                Ok(AbmSampleRequest {
                    sample_index: i64::try_from(sample_index)?,
                    seed: item.trim().parse::<i64>()?,
                    random_tape: None,
                })
            })
            .collect::<Result<Vec<_>>>()?;
        let result = run_abm_batch(plan, &requests, args.worker_threads)?;
        fs::write(&args.output, serde_json::to_vec_pretty(&result)?)?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "profile": sim_engine_runtime::ABM_PROFILE,
                "sample_count": result.len(),
                "sample_indexes": result.iter().map(|item| item.sample_index).collect::<Vec<_>>(),
            }))?
        );
    } else {
        let seed = args.seed.as_deref().unwrap_or("0").parse::<i64>()?;
        let random_tape = args
            .random_tape
            .as_ref()
            .map(fs::read)
            .transpose()?
            .map(|bytes| {
                serde_json::from_slice::<AbmRandomTape>(&bytes)
                    .map_err(|error| anyhow::anyhow!("invalid_random_tape: {error}"))
            })
            .transpose()?;
        let result = run_abm_plan_with_random_tape(&plan, seed, random_tape)?;
        fs::write(&args.output, serde_json::to_vec_pretty(&result)?)?;
        println!(
            "{}",
            serde_json::to_string(&serde_json::json!({
                "profile": result.profile,
                "ticks": result.ticks,
                "stop_reason": result.stop_reason,
                "events": result.events.len(),
            }))?
        );
    }
    Ok(())
}
