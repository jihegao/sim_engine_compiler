use std::{fs,path::PathBuf};
use anyhow::{Result,bail};
use clap::Parser;
use serde_json::Value;
use sim_engine_compiler_aot::{layers::{self,Artifact,BUSINESS_VERSION,CORE_VERSION},aircraft_support::lower_business};
#[derive(Parser)]
struct Args {
    input:PathBuf,output:PathBuf,
    #[arg(long,default_value="plan",value_parser=["business","core","plan"])] output_kind:String,
    #[arg(long,default_value="legacy-minute-v1",value_parser=["legacy-minute-v1","event-time-v2"])] semantic_profile:String,
}
fn main()->Result<()> {
    let args=Args::parse();let value:Value=serde_json::from_slice(&fs::read(args.input)?)?;
    let (business,core)=if value["version"]==CORE_VERSION {
        let core:Artifact=serde_json::from_value(value)?;layers::validate_core(&core)?;(None,core)
    }else{
        let business=if value["version"]==BUSINESS_VERSION {serde_json::from_value::<Artifact>(value)?}else{layers::import_business(&value,&args.semantic_profile)?};
        let core=lower_business(&business)?;(Some(business),core)
    };
    let output=match args.output_kind.as_str() {
        "business"=>{let Some(business)=business else{bail!("Core cannot reconstruct Business templates");};serde_json::to_value(business)?},
        "core"=>serde_json::to_value(core)?,_=>serde_json::to_value(layers::compile_core(&core)?)?,
    };
    if let Some(parent)=args.output.parent(){if !parent.as_os_str().is_empty(){fs::create_dir_all(parent)?;}}
    fs::write(args.output,serde_json::to_vec_pretty(&output)?)?;Ok(())
}
