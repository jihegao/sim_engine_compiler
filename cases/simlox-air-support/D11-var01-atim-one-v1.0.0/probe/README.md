# ATIM=1 exploratory run

The original contract, runner and roundtrip checker in this directory reproduce the source fingerprints for immutable run `d11-atim-one-probe-v100-ssh-20261001-01`. The probe had a question about initial and repeated PM behavior, so its output was not used as an accepted case. It yielded a timeline hypothesis for a new frozen contract. A separate guarded run `d11-atim-one-v100-ssh-20261001-02` under that contract supplied the acceptance candidate. The two runs' `model.log` and `report-raw.json` are byte-identical; raw files remain under ignored `../runs/`.
