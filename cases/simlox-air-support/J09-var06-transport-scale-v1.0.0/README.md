# J09.var06 SCTRT=2 excluded diagnostic

This [pre-run contract](contract.json) and [exact one-table input delta](exact-diff.json) tested global transport scale factor `SCTRT=2` against accepted E04 SLOW. The guarded native run `j09-var06-sctrt2-v100-ssh-20261004-01` completed import, export, calculation and report, but its strict import/export checker failed. Native export added ten optional `ScaleFactors` columns with null values. All six authored values survived, including `SCTRT=2`; the checker nonetheless required identical columns.

The [diagnostic record](diagnostic.json) pins the excluded run closure. This version is **not a published case**. A separate v1.0.1 package declares a lossless field-projection check before a fresh guarded run. Raw native files remain local in ignored `runs/`.
