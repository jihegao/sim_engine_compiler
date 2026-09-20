use std::{
    fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use serde::Serialize;
use sha2::{Digest, Sha256};

#[derive(Serialize)]
pub(crate) struct EvidenceFile {
    path: String,
    bytes: usize,
    sha256: String,
}

#[derive(Serialize)]
pub(crate) struct BuildIdentity {
    runtime_version: &'static str,
    build_profile: &'static str,
    profiling_feature: bool,
    python_feature: bool,
    target_os: &'static str,
    target_arch: &'static str,
    available_parallelism: usize,
    executable_path: String,
    executable_sha256: String,
    source_bundle_sha256: String,
    source_bundle_files: Vec<&'static str>,
    source_revision: Option<&'static str>,
    source_tree_state: Option<&'static str>,
    rustc_version: Option<&'static str>,
    source_diff: Option<EvidenceFile>,
    host_manifest: Option<EvidenceFile>,
}

const COMMON_SOURCE_FILES: &[(&str, &[u8])] = &[
    (
        "rust/runtime/src/bin/benchmark_support/mod.rs",
        include_bytes!("mod.rs"),
    ),
    ("rust/runtime/src/lib.rs", include_bytes!("../../lib.rs")),
    ("rust/runtime/src/plan.rs", include_bytes!("../../plan.rs")),
    ("rust/runtime/src/rng.rs", include_bytes!("../../rng.rs")),
    (
        "rust/runtime/src/runtime.rs",
        include_bytes!("../../runtime.rs"),
    ),
    (
        "rust/runtime/Cargo.toml",
        include_bytes!("../../../Cargo.toml"),
    ),
    (
        "rust/runtime/Cargo.lock",
        include_bytes!("../../../Cargo.lock"),
    ),
    (
        "rust/runtime/rust-toolchain.toml",
        include_bytes!("../../../rust-toolchain.toml"),
    ),
];

fn update_source_digest(hasher: &mut Sha256, name: &str, contents: &[u8]) {
    hasher.update((name.len() as u64).to_le_bytes());
    hasher.update(name.as_bytes());
    hasher.update((contents.len() as u64).to_le_bytes());
    hasher.update(contents);
}

fn evidence_file(path: Option<&Path>, label: &str) -> Result<Option<EvidenceFile>> {
    path.map(|path| {
        let contents = fs::read(path)
            .with_context(|| format!("read {label} evidence file {}", path.display()))?;
        Ok(EvidenceFile {
            path: path.display().to_string(),
            bytes: contents.len(),
            sha256: format!("{:x}", Sha256::digest(&contents)),
        })
    })
    .transpose()
}

pub(crate) fn build_identity(
    benchmark_source_name: &'static str,
    benchmark_source: &'static [u8],
    source_diff: Option<&Path>,
    host_manifest: Option<&Path>,
) -> Result<BuildIdentity> {
    let executable_path: PathBuf =
        std::env::current_exe().context("resolve benchmark executable")?;
    let executable = fs::read(&executable_path)
        .with_context(|| format!("read benchmark executable {}", executable_path.display()))?;
    let mut source_hasher = Sha256::new();
    let mut source_bundle_files = Vec::with_capacity(COMMON_SOURCE_FILES.len() + 1);
    for (name, contents) in COMMON_SOURCE_FILES {
        update_source_digest(&mut source_hasher, name, contents);
        source_bundle_files.push(*name);
    }
    update_source_digest(&mut source_hasher, benchmark_source_name, benchmark_source);
    source_bundle_files.push(benchmark_source_name);

    Ok(BuildIdentity {
        runtime_version: env!("CARGO_PKG_VERSION"),
        build_profile: if cfg!(debug_assertions) {
            "debug"
        } else {
            "release"
        },
        profiling_feature: cfg!(feature = "profiling"),
        python_feature: cfg!(feature = "python"),
        target_os: std::env::consts::OS,
        target_arch: std::env::consts::ARCH,
        available_parallelism: std::thread::available_parallelism()
            .map(|value| value.get())
            .unwrap_or(1),
        executable_path: executable_path.display().to_string(),
        executable_sha256: format!("{:x}", Sha256::digest(&executable)),
        source_bundle_sha256: format!("{:x}", source_hasher.finalize()),
        source_bundle_files,
        source_revision: option_env!("SIM_ENGINE_SOURCE_REVISION"),
        source_tree_state: option_env!("SIM_ENGINE_SOURCE_TREE_STATE"),
        rustc_version: option_env!("SIM_ENGINE_RUSTC_VERSION"),
        source_diff: evidence_file(source_diff, "source diff")?,
        host_manifest: evidence_file(host_manifest, "host manifest")?,
    })
}
