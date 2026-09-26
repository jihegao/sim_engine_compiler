# SIMLOX evidence provenance

Collected on Windows host 4700-3 on 2026-09-26. Requested `sim_engine_compiler` baseline: `e9b6391` (request metadata only; this workspace does not contain a compiler checkout). This is independent source-side SIMLOX evidence for later pairing. It makes no equivalence claim about canonical `simulation_inputs`.

## Sources and executable

- Installed executable: `C:\Program Files\Systecon\SIMLOX\Simlox.exe`. Windows version resource reports raw product version `2017.0.0.0`; file version string is empty. SHA-256, exact size, and path are in `manifest.json`.
- Documentation: `C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf` (996 pages); `...\Table relations\TableRelations_SIMLOX.pdf` (88 pages); `...\Table relations\DatabaseDictionary_SIMLOX.txt`; and `C:\Program Files\Systecon\SIMLOX\SIMLOX.chm`. The table diagram, page 3, says orange columns are indices, yellow are mandatory, and arrows point to defining data elements; solid arrows stay within a table group and dashed arrows cross groups. The PDF manual's external program control section (printed page 166) documents `-jexport`, `-jsonreport`, `-silent`, and `-close`. The CHM `sy_external_program_control.htm` gives the same syntax.
- Original Demo inputs: `C:\Users\Public\Documents\Systecon\SIMLOX\Demo\{aircraftorg,Torpedo Case,wbend,wbT2fix}.sxi`.
- Existing run: `C:\Users\user\Documents\Codex\2026-09-24\w\outputs\simlox-rerun-20260925`. Its `timings.json`, each `.1000.sxi`, `.run1.sxi`, `.run1.sxo`, and `.run1.log` were read only. Full sizes and SHA-256 digests appear in `manifest.json`.

## Export procedure and association

Each original Demo `.sxi` was opened and exported with `-silent -jexport <output> -close`. Each prior run 1 `.sxi` used the same command. Each prior run 1 `.sxo` was opened with `-silent -jsonreport <output> -close`. The twelve exact, absolute command lines and exit codes are in `manifest.json`; all exit codes were 0 and all twelve raw outputs are present in `raw/`. No `-calc` command was issued in this collection. No database was copied.

The prior run 1 logs explicitly name their input `.run1.sxi` and output `.run1.sxo` paths. In each case `.1000.sxi` and `.run1.sxi` have equal SHA-256. These facts verify a path and log based input/result association for each run 1 pair. The output files do not expose a separately checked embedded input hash or unique run identifier, so the association depends on the existing logs. `ResultSummary.NREP` is 1000 in all four exported reports, agreeing with exported `Control.NREPS`.

The original Demo exports and run 1 exports are distinct. The original `wbend` and `wbT2fix` `Control.NREPS` values are 100; run 1 has 1000. Their JSON table schemas also differ, with the later export including additional columns or tables, so a fieldwise proof that replication count was the only change has **not** been made. Original Demo export `Control.NREPS` for `aircraftorg` and `Torpedo Case` is recorded in `manifest.json`.

The command did not specify `-rpts`. The active/default report settings and any program registry settings are unknown. Exported report table names are captured per case in `manifest.json`; absent report tables do not prove the corresponding underlying metrics were absent from the simulation.

SIMLOX's `-jsonreport` wrote trailing commas before closing JSON arrays in all four raw report files. The raw bytes are preserved. For analysis only, trailing commas were removed in memory before parsing; `manifest.json` hashes cover the unmodified raw files.

## Run qualifications

The prior `aircraftorg`, `wbend`, and `wbT2fix` run 1 logs say input conversion completed with 0 errors and 0 warnings. `Torpedo Case` says 0 errors and 1 conversion warning: map layer `C:\Program Files\Simlox\Maps\World\world.shp` could not be read. Its run log also warns that mission and system percentile collection exceeded a 200 MB limit and that all `SYDT` percentiles could not be calculated. The report should not be used as complete percentile evidence. Timing values in the earlier `timings.json` are provenance only and were not remeasured.

No SIMLOX export failed. No compiler execution or canonical input pairing was performed.
