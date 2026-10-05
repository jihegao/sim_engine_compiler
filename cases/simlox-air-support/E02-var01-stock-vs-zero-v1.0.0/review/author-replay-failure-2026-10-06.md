# E02.var01 v1.0.0 author replay failure

The first read-only author replay failed 3 of 88 checks. Script SHA-256: `95d084f852d1533502911df205f0083ffa94d8299497bf398f2ad53da796f28c`. Original failed report SHA-256: `16e3888eea959880d43e5963ccaff2dce2a04e2ff48d12eab18d958e2990dc37` (the report's original UTF-8 BOM and CRLF bytes are preserved with `-text`). No native process was launched.

The two repair checks used a substring that also matched the nested direct-repair subtask completion, yielding two matches rather than one. The availability check used incorrect absolute integrals, 26.5/25.5 rather than the 72-row report's 35.5/34.5 hours. Both failures belong to the new replay script; all 24 accepted parent raw seals passed. The corrected read-only checker is versioned separately as v1.0.1.
