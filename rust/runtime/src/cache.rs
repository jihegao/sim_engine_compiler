//! Versioned binary cache envelope for immutable execution plans.

use anyhow::{Context, Result, bail};
use bincode::{config, serde as bincode_serde};
use serde::{Deserialize, Serialize};

use crate::plan::{ExecutionPlan, PLAN_VERSION};

const MAGIC: &[u8; 8] = b"SEPLAN\0\x03";
pub const PLAN_CACHE_FORMAT_VERSION: &str = "sim-engine-plan-cache/v3";

pub fn is_plan_cache(bytes: &[u8]) -> bool {
    bytes.starts_with(MAGIC)
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct CachedExecutionPlan {
    pub cache_format_version: String,
    pub compiler_version: String,
    pub source_model_sha256: Option<String>,
    pub adapter_contract_version: Option<String>,
    pub source_inputs_sha256: String,
    pub plan_version: String,
    pub plan_fingerprint: String,
    pub plan: ExecutionPlan,
}

// ExecutionPlan's optional MLIR index is omitted from JSON when absent. Bincode
// decodes struct fields positionally, so serialize the plan as JSON inside the
// binary envelope instead of applying that omission to a positional sequence.
#[derive(Deserialize, Serialize)]
struct CachedPlanWire {
    cache_format_version: String,
    compiler_version: String,
    source_model_sha256: Option<String>,
    adapter_contract_version: Option<String>,
    source_inputs_sha256: String,
    plan_version: String,
    plan_fingerprint: String,
    plan_json: Vec<u8>,
}

pub fn encode_plan_cache(
    plan: ExecutionPlan,
    compiler_version: &str,
    plan_fingerprint: &str,
) -> Result<Vec<u8>> {
    encode_plan_cache_with_identity(plan, compiler_version, plan_fingerprint, None, None)
}

pub fn encode_plan_cache_with_identity(
    plan: ExecutionPlan,
    compiler_version: &str,
    plan_fingerprint: &str,
    source_model_sha256: Option<&str>,
    adapter_contract_version: Option<&str>,
) -> Result<Vec<u8>> {
    plan.validate()?;
    let envelope = CachedExecutionPlan {
        cache_format_version: PLAN_CACHE_FORMAT_VERSION.to_owned(),
        compiler_version: compiler_version.to_owned(),
        source_model_sha256: source_model_sha256.map(str::to_owned),
        adapter_contract_version: adapter_contract_version.map(str::to_owned),
        source_inputs_sha256: plan.source_inputs_sha256.clone(),
        plan_version: plan.plan_version.clone(),
        plan_fingerprint: plan_fingerprint.to_owned(),
        plan,
    };
    let wire = CachedPlanWire {
        cache_format_version: envelope.cache_format_version,
        compiler_version: envelope.compiler_version,
        source_model_sha256: envelope.source_model_sha256,
        adapter_contract_version: envelope.adapter_contract_version,
        source_inputs_sha256: envelope.source_inputs_sha256,
        plan_version: envelope.plan_version,
        plan_fingerprint: envelope.plan_fingerprint,
        plan_json: serde_json::to_vec(&envelope.plan)?,
    };
    let payload = bincode_serde::encode_to_vec(&wire, config::standard())
        .context("encode execution plan cache")?;
    let mut output = Vec::with_capacity(MAGIC.len() + payload.len());
    output.extend_from_slice(MAGIC);
    output.extend_from_slice(&payload);
    Ok(output)
}

pub fn decode_plan_cache_with_identity(
    bytes: &[u8],
    expected_compiler_version: Option<&str>,
    expected_source_inputs_sha256: Option<&str>,
    expected_semantic_profile: Option<&str>,
    expected_source_model_sha256: Option<&str>,
    expected_adapter_contract_version: Option<&str>,
) -> Result<CachedExecutionPlan> {
    let envelope = decode_plan_cache(
        bytes,
        expected_compiler_version,
        expected_source_inputs_sha256,
        expected_semantic_profile,
    )?;
    if let Some(expected) = expected_source_model_sha256
        && envelope.source_model_sha256.as_deref() != Some(expected)
    {
        bail!("cached source model fingerprint does not match requested model");
    }
    if let Some(expected) = expected_adapter_contract_version
        && envelope.adapter_contract_version.as_deref() != Some(expected)
    {
        bail!("cached adapter contract does not match requested adapter");
    }
    Ok(envelope)
}

pub fn decode_plan_cache(
    bytes: &[u8],
    expected_compiler_version: Option<&str>,
    expected_source_inputs_sha256: Option<&str>,
    expected_semantic_profile: Option<&str>,
) -> Result<CachedExecutionPlan> {
    if !bytes.starts_with(MAGIC) {
        bail!("invalid execution plan cache magic");
    }
    let (wire, consumed): (CachedPlanWire, usize) =
        bincode_serde::decode_from_slice(&bytes[MAGIC.len()..], config::standard())
            .context("decode execution plan cache")?;
    if consumed != bytes.len() - MAGIC.len() {
        bail!("execution plan cache has trailing bytes");
    }
    let envelope = CachedExecutionPlan {
        cache_format_version: wire.cache_format_version,
        compiler_version: wire.compiler_version,
        source_model_sha256: wire.source_model_sha256,
        adapter_contract_version: wire.adapter_contract_version,
        source_inputs_sha256: wire.source_inputs_sha256,
        plan_version: wire.plan_version,
        plan_fingerprint: wire.plan_fingerprint,
        plan: ExecutionPlan::from_json_value(
            serde_json::from_slice(&wire.plan_json).context("decode cached plan JSON")?,
        )
        .context("decode cached plan JSON")?,
    };
    if envelope.cache_format_version != PLAN_CACHE_FORMAT_VERSION {
        bail!(
            "unsupported cache format {:?}",
            envelope.cache_format_version
        );
    }
    if envelope.plan_version != PLAN_VERSION || envelope.plan.plan_version != PLAN_VERSION {
        bail!("cached plan version does not match runtime plan version");
    }
    if envelope.source_inputs_sha256 != envelope.plan.source_inputs_sha256 {
        bail!("cached source fingerprint does not match embedded plan");
    }
    let actual_plan_fingerprint =
        ExecutionPlan::fingerprint(&serde_json::to_value(&envelope.plan)?)?;
    if envelope.plan_fingerprint != actual_plan_fingerprint {
        bail!("cached plan fingerprint does not match embedded plan");
    }
    if let Some(expected) = expected_compiler_version
        && envelope.compiler_version != expected
    {
        bail!(
            "cached compiler version {:?} does not match {:?}",
            envelope.compiler_version,
            expected
        );
    }
    if let Some(expected) = expected_source_inputs_sha256
        && envelope.source_inputs_sha256 != expected
    {
        bail!("cached source fingerprint does not match requested inputs");
    }
    if let Some(expected) = expected_semantic_profile
        && envelope.plan.semantic_profile != expected
    {
        bail!("cached semantic profile does not match requested profile");
    }
    envelope.plan.validate()?;
    Ok(envelope)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_plan() -> ExecutionPlan {
        ExecutionPlan {
            plan_version: PLAN_VERSION.to_owned(),
            domain: "aircraft-support".to_owned(),
            semantic_profile: "legacy-minute-v1".to_owned(),
            work_policy: "stable-topological-serial".to_owned(),
            rng_profile: "legacy-sequential-v1".to_owned(),
            source_inputs_sha256: "abc".to_owned(),
            duration_minutes: 1,
            natural_completion_enabled: false,
            phases: Vec::new(),
            aircraft: Vec::new(),
            missions: Vec::new(),
            activities: Vec::new(),
            resource_nodes: Vec::new(),
            components: Vec::new(),
            preventive_cycles: Vec::new(),
            supply_routes: Vec::new(),
            reliability_policy: None,
            component_groups: Vec::new(),
            component_instances: Vec::new(),
            resource_dispatch_index: None,
            unsupported_features: Vec::new(),
        }
    }

    #[test]
    fn cache_decode_rejects_failure_threshold_in_fused_plan() {
        let bytes = include_bytes!("../../../tests/fixtures/reliability/r1-fused-plan.json");
        let (plan, _) = ExecutionPlan::from_slice(bytes).unwrap();
        let plan_fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&plan).unwrap()).unwrap();
        let encoded = encode_plan_cache(plan, "compiler/v1", &plan_fingerprint).unwrap();
        let (mut wire, consumed) = bincode_serde::decode_from_slice::<CachedPlanWire, _>(
            &encoded[MAGIC.len()..],
            config::standard(),
        )
        .unwrap();
        assert_eq!(consumed, encoded.len() - MAGIC.len());
        let mut value: serde_json::Value = serde_json::from_slice(&wire.plan_json).unwrap();
        value["components"] = serde_json::json!([{"failure_threshold": 2}]);
        wire.plan_json = serde_json::to_vec(&value).unwrap();
        let payload = bincode_serde::encode_to_vec(&wire, config::standard()).unwrap();
        let mut tampered = MAGIC.to_vec();
        tampered.extend_from_slice(&payload);

        let error = decode_plan_cache(&tampered, Some("compiler/v1"), None, None).unwrap_err();
        assert!(
            format!("{error:#}").contains("failure_threshold_in_new_plan"),
            "{error:#}"
        );
    }

    #[test]
    fn cache_round_trip_and_identity_guards() {
        let plan = empty_plan();
        let plan_fingerprint =
            ExecutionPlan::fingerprint(&serde_json::to_value(&plan).unwrap()).unwrap();
        let bytes = encode_plan_cache(plan, "compiler/v1", &plan_fingerprint).unwrap();
        let cached = decode_plan_cache(
            &bytes,
            Some("compiler/v1"),
            Some("abc"),
            Some("legacy-minute-v1"),
        )
        .unwrap();
        assert_eq!(cached.plan_fingerprint, plan_fingerprint);
        assert!(decode_plan_cache(&bytes, Some("compiler/v2"), None, None).is_err());
        assert!(decode_plan_cache(&bytes, None, Some("other"), None).is_err());
        assert!(decode_plan_cache(&bytes, None, None, Some("event-time-v2")).is_err());
        let bytes = encode_plan_cache_with_identity(
            empty_plan(),
            "compiler/v1",
            &plan_fingerprint,
            Some("project-sha"),
            Some("adapter/v1"),
        )
        .unwrap();
        assert!(
            decode_plan_cache_with_identity(
                &bytes,
                Some("compiler/v1"),
                Some("abc"),
                Some("legacy-minute-v1"),
                Some("project-sha"),
                Some("adapter/v1"),
            )
            .is_ok()
        );
        assert!(
            decode_plan_cache_with_identity(
                &bytes,
                None,
                None,
                None,
                Some("other-project"),
                Some("adapter/v1"),
            )
            .is_err()
        );
        let invalid = encode_plan_cache(empty_plan(), "compiler/v1", "not-the-plan-sha").unwrap();
        assert!(decode_plan_cache(&invalid, Some("compiler/v1"), None, None).is_err());
    }
}
