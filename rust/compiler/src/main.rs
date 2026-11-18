use std::{
    fs,
    path::{Path, PathBuf},
    str::FromStr,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result, bail};
use clap::Parser;
use serde_json::Value;
use sha2::{Digest, Sha256};
use sim_engine_compiler_aot::{
    COMPILER_VERSION, compile_aircraft_support_with_profile, plan_cache_file_name,
};
use sim_engine_runtime::{
    ExecutionPlan, ObservationLevel, Runtime, decode_plan_cache, decode_plan_cache_with_identity,
    encode_plan_cache_with_identity,
};

#[derive(Parser)]
#[command(about = "AOT compile canonical aircraft-support inputs into a versioned Execution Plan")]
struct Args {
    input: PathBuf,
    output: PathBuf,
    #[arg(long)]
    cache_dir: Option<PathBuf>,
    #[arg(long, requires = "adapter_contract_version")]
    project_json: Option<PathBuf>,
    #[arg(long, requires = "project_json")]
    adapter_contract_version: Option<String>,
    #[arg(long)]
    json_output: Option<PathBuf>,
    #[arg(long)]
    run_output: Option<PathBuf>,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long)]
    until: Option<i64>,
    #[arg(long, default_value = "summary")]
    observation_level: String,
    #[arg(
        long,
        value_parser = ["legacy-minute-v1", "event-time-v2"],
        default_value = "event-time-v2"
    )]
    semantic_profile: String,
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_nanos();
    let file_name = path
        .file_name()
        .and_then(|value| value.to_str())
        .context("output path has no UTF-8 file name")?;
    let temporary =
        path.with_file_name(format!(".{file_name}.{}.{}.tmp", std::process::id(), stamp));
    fs::write(&temporary, bytes)?;
    fs::rename(&temporary, path)?;
    Ok(())
}

fn main() -> Result<()> {
    let args = Args::parse();
    let started = Instant::now();
    if args.project_json.is_some() && args.cache_dir.is_none() {
        bail!("--project-json requires --cache-dir so the project-keyed cache is durable");
    }

    let mut project_read_nanos = 0_u128;
    let mut project_parse_nanos = 0_u128;
    let mut project_fingerprint_nanos = 0_u128;
    let source_model_sha256 = if let Some(path) = args.project_json.as_ref() {
        let read_started = Instant::now();
        let bytes = fs::read(path)?;
        project_read_nanos = read_started.elapsed().as_nanos();
        let parse_started = Instant::now();
        let project: Value = serde_json::from_slice(&bytes)?;
        project_parse_nanos = parse_started.elapsed().as_nanos();
        let fingerprint_started = Instant::now();
        let canonical = ExecutionPlan::python_canonical(&project)?;
        let fingerprint = format!("{:x}", Sha256::digest(canonical.as_bytes()));
        project_fingerprint_nanos = fingerprint_started.elapsed().as_nanos();
        Some(fingerprint)
    } else {
        None
    };
    let adapter_digest = args
        .adapter_contract_version
        .as_ref()
        .map(|value| format!("{:x}", Sha256::digest(value.as_bytes())));
    let cache_name = |identity: &str| {
        plan_cache_file_name(
            identity,
            adapter_digest.as_deref(),
            COMPILER_VERSION,
            &args.semantic_profile,
        )
    };
    let mut cache_hit = false;
    let mut compile_nanos = 0_u128;
    let mut cache_decode_nanos = 0_u128;
    let mut run_init_nanos = 0_u128;
    let mut run_execute_nanos = 0_u128;

    let read_started = Instant::now();
    let input_bytes = fs::read(&args.input)?;
    let read_nanos = read_started.elapsed().as_nanos();
    let parse_started = Instant::now();
    let inputs: Value = serde_json::from_slice(&input_bytes)?;
    let parse_nanos = parse_started.elapsed().as_nanos();
    let fingerprint_started = Instant::now();
    let canonical = ExecutionPlan::python_canonical(&inputs)?;
    let source_inputs_sha256 = format!("{:x}", Sha256::digest(canonical.as_bytes()));
    let fingerprint_nanos = fingerprint_started.elapsed().as_nanos();

    let cache_identity = match source_model_sha256.as_deref() {
        Some(project) => format!(
            "{:x}",
            Sha256::digest(format!("{project}:{source_inputs_sha256}").as_bytes())
        ),
        None => source_inputs_sha256.clone(),
    };
    let cache_path = args
        .cache_dir
        .as_ref()
        .map(|directory| directory.join(cache_name(&cache_identity)));

    let mut resolved = None;
    if let Some(path) = cache_path.as_ref()
        && path.is_file()
    {
        let cache_started = Instant::now();
        let bytes = fs::read(path)?;
        let cached = if source_model_sha256.is_some() {
            decode_plan_cache_with_identity(
                &bytes,
                Some(COMPILER_VERSION),
                Some(&source_inputs_sha256),
                Some(&args.semantic_profile),
                source_model_sha256.as_deref(),
                args.adapter_contract_version.as_deref(),
            )?
        } else {
            decode_plan_cache(
                &bytes,
                Some(COMPILER_VERSION),
                Some(&source_inputs_sha256),
                Some(&args.semantic_profile),
            )?
        };
        cache_decode_nanos = cache_started.elapsed().as_nanos();
        cache_hit = true;
        resolved = Some((cached.plan, cached.plan_fingerprint, bytes));
    }

    if resolved.is_none() {
        let compile_started = Instant::now();
        let plan = compile_aircraft_support_with_profile(&inputs, &args.semantic_profile)?;
        compile_nanos = compile_started.elapsed().as_nanos();
        if plan.source_inputs_sha256 != source_inputs_sha256 {
            bail!("compiler source fingerprint does not match cache key");
        }
        let raw = serde_json::to_value(&plan)?;
        let plan_fingerprint = ExecutionPlan::fingerprint(&raw)?;
        let bytes = encode_plan_cache_with_identity(
            plan.clone(),
            COMPILER_VERSION,
            &plan_fingerprint,
            source_model_sha256.as_deref(),
            args.adapter_contract_version.as_deref(),
        )?;
        if let Some(path) = cache_path.as_ref() {
            write_atomic(path, &bytes)?;
        }
        resolved = Some((plan, plan_fingerprint, bytes));
    }
    let (plan, plan_fingerprint, cache_bytes) = resolved.context("plan was not resolved")?;

    let output_started = Instant::now();
    write_atomic(&args.output, &cache_bytes)?;
    if let Some(path) = args.json_output.as_ref() {
        let mut bytes = serde_json::to_vec_pretty(&plan)?;
        bytes.push(b'\n');
        write_atomic(path, &bytes)?;
    }
    let output_elapsed = output_started.elapsed();
    if let Some(path) = args.run_output.as_ref() {
        let observation_level = ObservationLevel::from_str(&args.observation_level)?;
        let init_started = Instant::now();
        let runtime = Runtime::new_with_observation(
            plan.clone(),
            plan_fingerprint.clone(),
            args.seed,
            observation_level,
        )?;
        run_init_nanos = init_started.elapsed().as_nanos();
        let run_started = Instant::now();
        let result = runtime.run(args.until)?;
        run_execute_nanos = run_started.elapsed().as_nanos();
        write_atomic(path, &serde_json::to_vec(&result)?)?;
    }
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "compiler_version": COMPILER_VERSION,
            "cache_hit": cache_hit,
            "semantic_profile": args.semantic_profile,
            "source_model_sha256": source_model_sha256,
            "adapter_contract_version": args.adapter_contract_version,
            "source_inputs_sha256": source_inputs_sha256,
            "plan_fingerprint": plan_fingerprint,
            "plan_bytes": cache_bytes.len(),
            "aircraft": plan.aircraft.len(),
            "missions": plan.missions.len(),
            "activities": plan.activities.len(),
            "timing_ns": {
                "project_read": project_read_nanos,
                "project_json_parse": project_parse_nanos,
                "project_fingerprint": project_fingerprint_nanos,
                "read": read_nanos,
                "json_parse": parse_nanos,
                "input_fingerprint": fingerprint_nanos,
                "compile": compile_nanos,
                "cache_decode": cache_decode_nanos,
                "output": output_elapsed.as_nanos(),
                "run_init": run_init_nanos,
                "run_execute": run_execute_nanos,
                "total": started.elapsed().as_nanos(),
            }
        }))?
    );
    Ok(())
}
