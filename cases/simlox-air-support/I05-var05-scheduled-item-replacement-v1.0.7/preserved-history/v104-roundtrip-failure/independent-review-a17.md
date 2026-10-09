# Independent review of I05.var05 v1.0.4 failure — A17

Decision: NO_GO after import/export; no behavioral claim. Independently parsed the sealed input/export without running a checker. Same 36 tables, same order, metadata, instance names/settings, and numerically equal authored rows. Identified exactly 35 representation differences: 24 integral `double` cells encoded as JSON integers and 11 authored-empty tables encoded with one correctly sized all-null row. The change table remains appended at table index 35; `TIMEC` is represented as 5 instead of 5.0. The checker hardcodes 26 populated tables though authored input has 25 and rejects the observed JSON number representation. No calculation/report was run. Do not rerun v1.0.4.

This review was read-only: no checker, SSH or native command.
