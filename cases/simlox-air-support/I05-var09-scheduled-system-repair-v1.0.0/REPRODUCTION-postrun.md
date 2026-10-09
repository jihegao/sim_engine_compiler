# Sealed postrun replay on4700-3

Use the existing i05-var08-pm-location worktree and exact original/recovered/accepted-D01 raw files in evidence-reference.json. Verify hashes before reading. Run using the pinned current Python3.12.14 (10d845f5...) with -X utf8 -B:

```
python -X utf8 -B cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0/check_model.py --self-check
python -X utf8 -B cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0/author_reader.py --self-check
python -X utf8 -B cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0/check_model.py cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0/runs/i05-var09-system-repair-v100-ssh-20261010-01
python -X utf8 -B cases/simlox-air-support/I05-var09-scheduled-system-repair-v1.0.0/author_reader.py --arm child --model-log tmp/i05-var09-native-v100-20261010-01/model.log --report tmp/i05-var09-native-v100-20261010-01/report-raw.json
```

These are read-only author checking replays, not new native runs or independent signatures. Synthetic positives exercise predicates only. Independent receipt/own audit sources are preserved under review; their complete custody audit ran before publication metadata advanced and requires the original job paths, unchanged source snapshot and proprietary originals. Do not represent that historical all-source audit as a portable checker or rerun it against changed live publication metadata. The prepublication index is archived with its originalSHA in evidence-reference.json; frozen manifests and historical accounting are never repinned.

Do not invoke the old native transport/runID again: physical and recovered directories now exist and its guards reject reuse. A future native experiment requires new version/runID, fresh source/tool freeze and all independent/realSSH gates. No GUI functionality validation is scheduled. Missing host evidence is an explicit inability to reproduce, not grounds for synthetic replacement or acceptance.
