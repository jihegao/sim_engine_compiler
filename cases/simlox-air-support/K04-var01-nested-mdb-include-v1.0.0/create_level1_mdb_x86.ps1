param([Parameter(Mandatory=$true)][string]$Source, [Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::Is64BitProcess) { throw '32-bit Windows PowerShell required' }
$sourceObj = Get-Content -LiteralPath $Source -Raw -Encoding UTF8 | ConvertFrom-Json
if ($sourceObj.table -ne 'IncludeFiles' -or ($sourceObj.columns -join ',') -ne 'INCFN,INCCO,NOTE' -or @($sourceObj.rows).Count -ne 1) { throw 'level1 source differs' }
$row = $sourceObj.rows[0]
if ($row[1] -ne 'Required base station' -or $null -ne $row[2] -or $row[0] -ne (Join-Path (Split-Path $Output -Parent) 'level2.mdb') -or $row[0].Length -gt 255) { throw 'nested path differs' }
if (Test-Path -LiteralPath $Output) { throw 'database output exists' }
$catalog = New-Object -ComObject ADOX.Catalog
$null = $catalog.Create("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output;Jet OLEDB:Engine Type=5")
$catalog.ActiveConnection.Close(); $catalog = $null
$connection = New-Object -ComObject ADODB.Connection
try {
    $connection.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output")
    $affected = 0
    $null = $connection.Execute('CREATE TABLE [IncludeFiles] ([INCFN] TEXT(255), [INCCO] TEXT(255), [NOTE] MEMO)', [ref]$affected)
    $quoted = $row[0].Replace("'", "''")
    $null = $connection.Execute("INSERT INTO [IncludeFiles] ([INCFN],[INCCO],[NOTE]) VALUES ('$quoted','Required base station',NULL)", [ref]$affected)
} finally { if ($connection.State -eq 1) { $connection.Close() } }
$odbc = [System.Data.Odbc.OdbcConnection]::new("Driver={Microsoft Access Driver (*.mdb)};DBQ=$Output;ReadOnly=1;")
try {
    $odbc.Open()
    $names = @($odbc.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' } | ForEach-Object { [string]$_['TABLE_NAME'] } | Sort-Object)
    if ($names.Count -ne 1 -or $names[0] -ne 'IncludeFiles') { throw 'level1 user tables differ' }
    $command = $odbc.CreateCommand(); $command.CommandText = 'SELECT [INCFN],[INCCO],[NOTE] FROM [IncludeFiles]'
    $reader = $command.ExecuteReader(); $rows = @()
    while ($reader.Read()) { $rows += @([ordered]@{INCFN=$reader.GetString(0);INCCO=$reader.GetString(1);NOTE=if($reader.IsDBNull(2)){$null}else{$reader.GetString(2)}}) }
    $reader.Close()
    if ($rows.Count -ne 1 -or $rows[0].INCFN -ne $row[0] -or $rows[0].INCCO -ne $row[1] -or $null -ne $rows[0].NOTE) { throw 'level1 ODBC readback differs' }
    [ordered]@{schema='simlox-k04-var01-level1-readback/v1';driver='Microsoft Access Driver (*.mdb)';process_bitness=32;tables=$names;rows=$rows;database_bytes=(Get-Item -LiteralPath $Output).Length;database_sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($Output,'.readback.json')) -Encoding UTF8
} finally { $odbc.Close() }
