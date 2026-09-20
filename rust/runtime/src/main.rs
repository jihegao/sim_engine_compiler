use std::{fs, path::PathBuf};

use anyhow::Result;
use clap::Parser;
use sim_engine_runtime::{ExecutionPlan, Runtime};

#[derive(Parser)]
#[command(about = "Execute an aircraft-support Execution Plan with the independent Rust runtime")]
struct Args {
    plan: PathBuf,
    output: PathBuf,
    #[arg(long, default_value_t = 0)]
    seed: u64,
    #[arg(long)]
    until: Option<i64>,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let bytes = fs::read(&args.plan)?;
    let (plan, raw) = ExecutionPlan::from_slice(&bytes)?;
    let fingerprint = ExecutionPlan::fingerprint(&raw)?;
    let result = Runtime::new(plan, fingerprint, args.seed)?.run(args.until)?;
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&args.output, serde_json::to_vec_pretty(&result)?)?;
    println!(
        "{}",
        serde_json::to_string(&serde_json::json!({
            "plan_fingerprint": result.plan_fingerprint, "time": result.time,
            "stop_reason": result.stop_reason, "events": result.trace.len(),
        }))?
    );
    Ok(())
}
