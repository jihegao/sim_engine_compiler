pub mod aircraft_support;
pub mod canonical_batch;

pub use aircraft_support::{
    COMPILER_VERSION, compile_aircraft_support, compile_aircraft_support_with_profile,
};
pub use canonical_batch::{
    CANONICAL_BATCH_CONTRACT_VERSION, CanonicalBatchResult, CanonicalSampleRequest,
    run_canonical_batch,
};

#[cfg(feature = "python")]
mod python;
