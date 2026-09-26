$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$prior = 'C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence'
$out = Join-Path $repo 'data\local\j35-contract-probes\p0\rust-rebuild'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$env:RUSTUP_HOME = Join-Path $prior 'rustup-home'
$env:CARGO_HOME = Join-Path $prior 'cargo-home'
$env:RUSTUP_TOOLCHAIN = '1.90.0-x86_64-pc-windows-gnu'
$env:CARGO_TARGET_DIR = Join-Path $out 'target'
$toolBin = Join-Path $env:RUSTUP_HOME 'toolchains\1.90.0-x86_64-pc-windows-gnu\bin'
$selfContained = Join-Path $env:RUSTUP_HOME 'toolchains\1.90.0-x86_64-pc-windows-gnu\lib\rustlib\x86_64-pc-windows-gnu\bin\self-contained'
$llvm = Join-Path $prior 'llvm-mingw\llvm-mingw-20260519-ucrt-x86_64\bin'
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = Join-Path $selfContained 'x86_64-w64-mingw32-gcc.exe'
$env:PATH = $toolBin + ';' + $llvm + ';' + $selfContained + ';' + (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:PATH
& (Join-Path $toolBin 'rustc.exe') --version | Set-Content (Join-Path $out 'rustc-version.txt')
& (Join-Path $toolBin 'cargo.exe') --version | Set-Content (Join-Path $out 'cargo-version.txt')
$watch = [Diagnostics.Stopwatch]::StartNew()
$ErrorActionPreference = 'Continue' # Cargo writes normal build progress to stderr.
& (Join-Path $toolBin 'cargo.exe') build --release --locked --offline --manifest-path (Join-Path $repo 'rust\runtime\Cargo.toml') *> (Join-Path $out 'cargo-build.log')
$code = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$watch.Stop()
$exe = Join-Path $env:CARGO_TARGET_DIR 'release\sim-engine-runtime.exe'
$result = [pscustomobject]@{
    exit_code = $code
    wall_seconds = $watch.Elapsed.TotalSeconds
    rustc_version = (Get-Content (Join-Path $out 'rustc-version.txt') -Raw).Trim()
    cargo_version = (Get-Content (Join-Path $out 'cargo-version.txt') -Raw).Trim()
    executable = $exe
    executable_sha256 = if (Test-Path $exe) { (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
}
$result | ConvertTo-Json | Set-Content (Join-Path $out 'result.json') -Encoding UTF8
$result
if ($code -ne 0 -or !(Test-Path $exe)) { throw 'Offline Rust GNU release build failed; see cargo-build.log' }
