use std::collections::BTreeSet;

use clap::Parser;
use serde::Serialize;

const REPEATED_ORACLE_LIMIT: i64 = 100_000;
const MAX_EXACT_F64_INTEGER: f64 = 9_007_199_254_740_992.0;

#[derive(Debug, Parser)]
#[command(about = "Compare repeated and bulk continuous-state advancement")]
struct Args {
    /// Include every generated case in the JSON output instead of representative examples only.
    #[arg(long)]
    include_cases: bool,

    /// Emit compact JSON instead of pretty-printed JSON.
    #[arg(long)]
    compact: bool,
}

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
enum Category {
    Equal,
    Mismatch,
    Fallback,
}

#[derive(Clone, Copy, Debug, Default, Serialize)]
struct CategoryCounts {
    equal: u64,
    mismatch: u64,
    fallback: u64,
}

impl CategoryCounts {
    fn record(&mut self, category: Category) {
        match category {
            Category::Equal => self.equal += 1,
            Category::Mismatch => self.mismatch += 1,
            Category::Fallback => self.fallback += 1,
        }
    }

    #[cfg(test)]
    fn total(self) -> u64 {
        self.equal + self.mismatch + self.fallback
    }
}

#[derive(Clone, Copy, Debug, Default, Serialize)]
struct GuardCounts {
    accepted_equal: u64,
    accepted_mismatch: u64,
    rejected_equal: u64,
    rejected_mismatch: u64,
    rejected_fallback: u64,
    accepted_unverified: u64,
}

#[derive(Debug, Serialize)]
struct CaseRecord {
    lane: &'static str,
    label: String,
    remaining: String,
    remaining_bits: Option<String>,
    span: String,
    category: Category,
    guard_action: &'static str,
    guard_reason: Option<&'static str>,
    fallback_reason: Option<&'static str>,
    repeated_remaining: Option<String>,
    repeated_bits: Option<String>,
    bulk_remaining: Option<String>,
    bulk_bits: Option<String>,
    due_tick_before: Option<String>,
    repeated_due_tick_after: Option<String>,
    bulk_due_tick_after: Option<String>,
    absolute_due_tick_preserved: Option<bool>,
}

#[derive(Debug, Serialize)]
struct LaneSummary {
    category_counts: CategoryCounts,
    guard_counts: GuardCounts,
}

#[derive(Debug, Serialize)]
struct ExperimentSummary {
    schema_version: &'static str,
    repeated_oracle_limit: i64,
    exact_f64_integer_envelope: &'static str,
    generated_case_count: u64,
    categories: CategoryCounts,
    jobs: LaneSummary,
    failures: LaneSummary,
    guarded_fast_path_supported: bool,
    conclusion: &'static str,
    cases: Vec<CaseRecord>,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let summary = run_experiment(args.include_cases);
    if args.compact {
        println!("{}", serde_json::to_string(&summary)?);
    } else {
        println!("{}", serde_json::to_string_pretty(&summary)?);
    }
    Ok(())
}

fn run_experiment(include_cases: bool) -> ExperimentSummary {
    let mut records = Vec::new();

    for (label, remaining, span) in job_cases() {
        records.push(compare_job(label, remaining, span));
    }
    for (label, remaining, span) in failure_cases() {
        records.push(compare_failure(label, remaining, span));
    }

    let generated_case_count = records.len() as u64;
    let jobs = summarize_lane(&records, "job_i64");
    let failures = summarize_lane(&records, "failure_f64");
    let mut categories = CategoryCounts::default();
    for record in &records {
        categories.record(record.category);
    }

    let guarded_fast_path_supported = jobs.guard_counts.accepted_mismatch == 0
        && failures.guard_counts.accepted_mismatch == 0
        && jobs.guard_counts.accepted_equal > 0
        && failures.guard_counts.accepted_equal > 0
        && failures.guard_counts.rejected_mismatch > 0;

    let cases = if include_cases {
        records
    } else {
        representative_cases(records)
    };

    ExperimentSummary {
        schema_version: "continuous-advance-experiment/v1",
        repeated_oracle_limit: REPEATED_ORACLE_LIMIT,
        exact_f64_integer_envelope: "0 < remaining <= 2^53; 0 <= span < due_tick",
        generated_case_count,
        categories,
        jobs,
        failures,
        guarded_fast_path_supported,
        conclusion: "Use checked subtraction for valid i64 jobs. For f64 failure timers, bulk subtraction is bit-exact in the tested <=2^53 envelope; retain repeated decrement outside that guard and for non-finite, non-positive, due-crossing, or unverified huge-span inputs.",
        cases,
    }
}

fn summarize_lane(records: &[CaseRecord], lane: &str) -> LaneSummary {
    let mut category_counts = CategoryCounts::default();
    let mut guard_counts = GuardCounts::default();
    for record in records.iter().filter(|record| record.lane == lane) {
        category_counts.record(record.category);
        match (record.guard_action, record.category) {
            ("bulk", Category::Equal) => guard_counts.accepted_equal += 1,
            ("bulk", Category::Mismatch) => guard_counts.accepted_mismatch += 1,
            ("bulk", Category::Fallback) => guard_counts.accepted_unverified += 1,
            ("repeated_fallback", Category::Equal) => guard_counts.rejected_equal += 1,
            ("repeated_fallback", Category::Mismatch) => guard_counts.rejected_mismatch += 1,
            ("repeated_fallback", Category::Fallback) => guard_counts.rejected_fallback += 1,
            _ => unreachable!("unknown guard action"),
        }
    }
    LaneSummary {
        category_counts,
        guard_counts,
    }
}

fn representative_cases(records: Vec<CaseRecord>) -> Vec<CaseRecord> {
    let mut selected = Vec::new();
    let mut seen = BTreeSet::new();
    for record in records {
        let key = (
            record.lane,
            match record.category {
                Category::Equal => 0_u8,
                Category::Mismatch => 1,
                Category::Fallback => 2,
            },
            record.fallback_reason,
            record.guard_reason,
        );
        if seen.insert(key) {
            selected.push(record);
        }
    }
    selected
}

fn job_cases() -> Vec<(String, i64, i64)> {
    let mut cases = vec![
        ("boundary/min".to_owned(), i64::MIN, 1),
        ("boundary/negative".to_owned(), -1, 0),
        ("boundary/zero".to_owned(), 0, 0),
        ("boundary/negative-span".to_owned(), 10, -1),
        ("boundary/due-crossing".to_owned(), 1, 1),
        ("boundary/max-minus-one".to_owned(), i64::MAX, i64::MAX - 1),
        (
            "boundary/oracle-budget".to_owned(),
            i64::MAX,
            REPEATED_ORACLE_LIMIT + 1,
        ),
    ];
    let remaining_values = [
        1,
        2,
        3,
        7,
        31,
        255,
        4_096,
        (1_i64 << 31) - 1,
        (1_i64 << 53) - 1,
        1_i64 << 53,
        i64::MAX,
    ];
    let spans = [0, 1, 2, 3, 7, 31, 255, 4_095];
    for remaining in remaining_values {
        for span in spans {
            cases.push((format!("grid/{remaining}/{span}"), remaining, span));
        }
        if remaining > 0 {
            cases.push((
                format!("grid/{remaining}/due-minus-one"),
                remaining,
                remaining - 1,
            ));
            cases.push((format!("grid/{remaining}/due"), remaining, remaining));
        }
    }
    cases
}

fn failure_cases() -> Vec<(String, f64, i64)> {
    let mut cases = vec![
        ("boundary/nan".to_owned(), f64::NAN, 1),
        ("boundary/positive-infinity".to_owned(), f64::INFINITY, 1),
        (
            "boundary/negative-infinity".to_owned(),
            f64::NEG_INFINITY,
            1,
        ),
        ("boundary/negative".to_owned(), -1.0, 0),
        ("boundary/negative-zero".to_owned(), -0.0, 0),
        ("boundary/zero".to_owned(), 0.0, 0),
        ("boundary/min-subnormal".to_owned(), f64::from_bits(1), 0),
        ("boundary/negative-span".to_owned(), 10.25, -1),
        ("boundary/due-crossing".to_owned(), 1.25, 2),
        (
            "boundary/first-unsafe-mismatch".to_owned(),
            MAX_EXACT_F64_INTEGER + 2.0,
            2,
        ),
        (
            "boundary/unsafe-sticky-mismatch".to_owned(),
            MAX_EXACT_F64_INTEGER + 4.0,
            3,
        ),
        ("boundary/huge-span".to_owned(), f64::MAX, (1_i64 << 53) + 1),
        ("boundary/max-finite".to_owned(), f64::MAX, 1),
    ];

    let whole_values = [
        1_u64,
        2,
        3,
        7,
        31,
        255,
        1_023,
        65_535,
        1 << 20,
        1 << 32,
        1 << 48,
        (1 << 52) - 2,
        1 << 52,
        (1 << 53) - 2,
        1 << 53,
    ];
    let fractions = [0.0, 0.25, 0.5, 0.75];
    let spans = [0, 1, 2, 3, 7, 31, 255, 4_095];
    for whole in whole_values {
        for fraction in fractions {
            let base = whole as f64 + fraction;
            for (variant, remaining) in [
                ("down", next_down(base)),
                ("base", base),
                ("up", next_up(base)),
            ] {
                for span in spans {
                    cases.push((
                        format!("grid/{whole}/{fraction}/{variant}/{span}"),
                        remaining,
                        span,
                    ));
                }
            }
        }
    }
    cases
}

fn compare_job(label: String, remaining: i64, span: i64) -> CaseRecord {
    let base = |category, guard_action, guard_reason, fallback_reason| CaseRecord {
        lane: "job_i64",
        label: label.clone(),
        remaining: remaining.to_string(),
        remaining_bits: None,
        span: span.to_string(),
        category,
        guard_action,
        guard_reason,
        fallback_reason,
        repeated_remaining: None,
        repeated_bits: None,
        bulk_remaining: None,
        bulk_bits: None,
        due_tick_before: (remaining > 0).then(|| remaining.to_string()),
        repeated_due_tick_after: None,
        bulk_due_tick_after: None,
        absolute_due_tick_preserved: None,
    };

    let invalid_reason = if remaining <= 0 {
        Some("non_positive_remaining")
    } else if span < 0 {
        Some("negative_span")
    } else if span >= remaining {
        Some("span_reaches_or_crosses_due_tick")
    } else {
        None
    };
    if let Some(reason) = invalid_reason {
        return base(
            Category::Fallback,
            "repeated_fallback",
            Some(reason),
            Some(reason),
        );
    }

    if span > REPEATED_ORACLE_LIMIT {
        return base(
            Category::Fallback,
            "bulk",
            None,
            Some("span_exceeds_repeated_oracle_limit"),
        );
    }

    let mut repeated = remaining;
    for _ in 0..span {
        repeated -= 1;
    }
    let bulk = remaining
        .checked_sub(span)
        .expect("validated positive countdown cannot overflow");
    let repeated_due = repeated;
    let bulk_due = bulk;
    let absolute_due_preserved = span.checked_add(repeated_due) == Some(remaining)
        && span.checked_add(bulk_due) == Some(remaining);
    let category = if repeated == bulk && absolute_due_preserved {
        Category::Equal
    } else {
        Category::Mismatch
    };

    let mut record = base(category, "bulk", None, None);
    record.repeated_remaining = Some(repeated.to_string());
    record.bulk_remaining = Some(bulk.to_string());
    record.repeated_due_tick_after = Some(repeated_due.to_string());
    record.bulk_due_tick_after = Some(bulk_due.to_string());
    record.absolute_due_tick_preserved = Some(absolute_due_preserved);
    record
}

fn compare_failure(label: String, remaining: f64, span: i64) -> CaseRecord {
    let due_before = failure_due_ticks(remaining);
    let guard_reason = failure_guard_reason(remaining, span, due_before);
    let guard_action = if guard_reason.is_none() {
        "bulk"
    } else {
        "repeated_fallback"
    };
    let base = |category, fallback_reason| CaseRecord {
        lane: "failure_f64",
        label: label.clone(),
        remaining: format_float(remaining),
        remaining_bits: Some(format_bits(remaining)),
        span: span.to_string(),
        category,
        guard_action,
        guard_reason,
        fallback_reason,
        repeated_remaining: None,
        repeated_bits: None,
        bulk_remaining: None,
        bulk_bits: None,
        due_tick_before: due_before.map(|due| due.to_string()),
        repeated_due_tick_after: None,
        bulk_due_tick_after: None,
        absolute_due_tick_preserved: None,
    };

    let validation_reason = if !remaining.is_finite() {
        Some("non_finite_remaining")
    } else if remaining <= 0.0 {
        Some("non_positive_remaining")
    } else if span < 0 {
        Some("negative_span")
    } else if due_before.is_some_and(|due| span >= due) {
        Some("span_reaches_or_crosses_due_tick")
    } else {
        None
    };
    if let Some(reason) = validation_reason {
        return base(Category::Fallback, Some(reason));
    }
    if span > REPEATED_ORACLE_LIMIT {
        return base(
            Category::Fallback,
            Some("span_exceeds_repeated_oracle_limit"),
        );
    }

    let mut repeated = remaining;
    for _ in 0..span {
        repeated -= 1.0;
    }
    let bulk = remaining - span as f64;
    let repeated_due = failure_due_ticks(repeated);
    let bulk_due = failure_due_ticks(bulk);
    let absolute_due_preserved = match (due_before, repeated_due, bulk_due) {
        (Some(before), Some(repeated_after), Some(bulk_after)) => {
            span.checked_add(repeated_after) == Some(before)
                && span.checked_add(bulk_after) == Some(before)
        }
        _ => false,
    };
    let category = if repeated.to_bits() == bulk.to_bits()
        && repeated_due == bulk_due
        && absolute_due_preserved
    {
        Category::Equal
    } else {
        Category::Mismatch
    };

    let mut record = base(category, None);
    record.repeated_remaining = Some(format_float(repeated));
    record.repeated_bits = Some(format_bits(repeated));
    record.bulk_remaining = Some(format_float(bulk));
    record.bulk_bits = Some(format_bits(bulk));
    record.repeated_due_tick_after = repeated_due.map(|due| due.to_string());
    record.bulk_due_tick_after = bulk_due.map(|due| due.to_string());
    record.absolute_due_tick_preserved = Some(absolute_due_preserved);
    record
}

fn failure_guard_reason(
    remaining: f64,
    span: i64,
    due_before: Option<i64>,
) -> Option<&'static str> {
    if !remaining.is_finite() {
        Some("non_finite_remaining")
    } else if remaining <= 0.0 {
        Some("non_positive_remaining")
    } else if span < 0 {
        Some("negative_span")
    } else if due_before.is_some_and(|due| span >= due) {
        Some("span_reaches_or_crosses_due_tick")
    } else if remaining > MAX_EXACT_F64_INTEGER {
        Some("remaining_exceeds_exact_integer_envelope")
    } else if span > MAX_EXACT_F64_INTEGER as i64 {
        Some("span_exceeds_exact_integer_envelope")
    } else {
        None
    }
}

fn failure_due_ticks(remaining: f64) -> Option<i64> {
    if !remaining.is_finite() || remaining <= 0.0 {
        None
    } else if remaining <= 1.0 {
        Some(1)
    } else if remaining >= i64::MAX as f64 {
        Some(i64::MAX)
    } else {
        Some((remaining.ceil() as i64).max(1))
    }
}

fn next_up(value: f64) -> f64 {
    if value.is_nan() || value == f64::INFINITY {
        value
    } else if value == -0.0 {
        f64::from_bits(1)
    } else if value >= 0.0 {
        f64::from_bits(value.to_bits() + 1)
    } else {
        f64::from_bits(value.to_bits() - 1)
    }
}

fn next_down(value: f64) -> f64 {
    if value.is_nan() || value == f64::NEG_INFINITY {
        value
    } else if value == 0.0 {
        -f64::from_bits(1)
    } else if value > 0.0 {
        f64::from_bits(value.to_bits() - 1)
    } else {
        f64::from_bits(value.to_bits() + 1)
    }
}

fn format_float(value: f64) -> String {
    match value.classify() {
        std::num::FpCategory::Nan => "NaN".to_owned(),
        _ if value == f64::INFINITY => "+Infinity".to_owned(),
        _ if value == f64::NEG_INFINITY => "-Infinity".to_owned(),
        _ => format!("{value:?}"),
    }
}

fn format_bits(value: f64) -> String {
    format!("0x{:016x}", value.to_bits())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn i64_bulk_matches_repeated_for_valid_grid() {
        let summary = run_experiment(false);
        assert_eq!(summary.jobs.category_counts.mismatch, 0);
        assert!(summary.jobs.category_counts.equal > 0);
        assert!(summary.jobs.category_counts.fallback > 0);
        assert_eq!(summary.jobs.guard_counts.accepted_mismatch, 0);
    }

    #[test]
    fn f64_guard_accepts_only_bit_exact_comparisons() {
        let summary = run_experiment(false);
        assert!(summary.guarded_fast_path_supported);
        assert_eq!(summary.failures.guard_counts.accepted_mismatch, 0);
        assert!(summary.failures.guard_counts.accepted_equal > 0);
        assert!(summary.failures.guard_counts.rejected_mismatch > 0);
    }

    #[test]
    fn naive_f64_bulk_has_a_boundary_mismatch() {
        let record = compare_failure("test".to_owned(), MAX_EXACT_F64_INTEGER + 2.0, 2);
        assert!(matches!(record.category, Category::Mismatch));
        assert_eq!(record.guard_action, "repeated_fallback");
        assert_ne!(record.repeated_bits, record.bulk_bits);
    }

    #[test]
    fn nan_infinity_and_huge_span_are_explicit_fallbacks() {
        for remaining in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            let record = compare_failure("non-finite".to_owned(), remaining, 1);
            assert!(matches!(record.category, Category::Fallback));
            assert_eq!(record.fallback_reason, Some("non_finite_remaining"));
        }

        let huge = compare_failure("huge".to_owned(), f64::MAX, (1_i64 << 53) + 1);
        assert!(matches!(huge.category, Category::Fallback));
        assert_eq!(
            huge.fallback_reason,
            Some("span_exceeds_repeated_oracle_limit")
        );
        assert_eq!(huge.guard_action, "repeated_fallback");
    }

    #[test]
    fn due_tick_is_preserved_inside_guard() {
        for (remaining, span) in [(5.581_821, 4), (120.25, 31), (65_535.75, 4_095)] {
            let record = compare_failure("due".to_owned(), remaining, span);
            assert!(matches!(record.category, Category::Equal));
            assert_eq!(record.guard_action, "bulk");
            assert_eq!(record.absolute_due_tick_preserved, Some(true));
        }
    }

    #[test]
    fn generated_grid_exercises_all_categories() {
        let summary = run_experiment(false);
        assert_eq!(summary.categories.total(), summary.generated_case_count);
        assert!(summary.categories.equal > 1_000);
        assert!(summary.categories.mismatch > 0);
        assert!(summary.categories.fallback > 0);
    }
}
