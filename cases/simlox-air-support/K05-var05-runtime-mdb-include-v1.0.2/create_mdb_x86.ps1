param([Parameter(Mandatory=$true)][string]$Source, [Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitOperatingSystem -or [Environment]::Is64BitProcess) { throw '32-bit Windows PowerShell required' }
$sourceObj = Get-Content -LiteralPath $Source -Raw -Encoding UTF8 | ConvertFrom-Json
if ($sourceObj.table -ne 'Station' -or ($sourceObj.columns -join ',') -ne 'STID,DESCR,QTY,TYPE' -or
    @($sourceObj.rows).Count -ne 1 -or ($sourceObj.rows[0] -join '|') -ne 'BASE-01|Teaching base|1|WS') { throw 'database source differs' }
if (Test-Path -LiteralPath $Output) { throw 'database output exists' }
$catalog = New-Object -ComObject ADOX.Catalog
$null = $catalog.Create("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output;Jet OLEDB:Engine Type=5")
$catalog.ActiveConnection.Close()
$catalog = $null
$connection = New-Object -ComObject ADODB.Connection
try {
    $connection.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output")
    $affected = 0
    $null = $connection.Execute('CREATE TABLE [Station] ([STID] TEXT(255), [DESCR] TEXT(255), [QTY] INTEGER, [TYPE] TEXT(255))', [ref]$affected)
    $null = $connection.Execute("INSERT INTO [Station] ([STID],[DESCR],[QTY],[TYPE]) VALUES ('BASE-01','Teaching base',1,'WS')", [ref]$affected)
} finally { if ($connection.State -eq 1) { $connection.Close() } }
$odbc = [System.Data.Odbc.OdbcConnection]::new("Driver={Microsoft Access Driver (*.mdb)};DBQ=$Output;ReadOnly=1;")
try {
    $odbc.Open()
    $command = $odbc.CreateCommand()
    $command.CommandText = 'SELECT [STID],[DESCR],[QTY],[TYPE] FROM [Station] ORDER BY [STID]'
    $reader = $command.ExecuteReader()
    $rows = @()
    while ($reader.Read()) { $rows += @([ordered]@{ STID=$reader.GetString(0); DESCR=$reader.GetString(1); QTY=$reader.GetInt32(2); TYPE=$reader.GetString(3) }) }
    $reader.Close()
    if ($rows.Count -ne 1 -or $rows[0].STID -ne 'BASE-01' -or $rows[0].DESCR -ne 'Teaching base' -or $rows[0].QTY -ne 1 -or $rows[0].TYPE -ne 'WS') { throw 'ODBC readback differs' }
    [ordered]@{schema='simlox-k05-var05-db-readback/v1';driver='Microsoft Access Driver (*.mdb)';provider='Microsoft.Jet.OLEDB.4.0';process_bitness=32;tables=@('Station');rows=$rows;database_bytes=(Get-Item -LiteralPath $Output).Length;database_sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($Output,'.readback.json')) -Encoding UTF8
} finally { $odbc.Close() }
