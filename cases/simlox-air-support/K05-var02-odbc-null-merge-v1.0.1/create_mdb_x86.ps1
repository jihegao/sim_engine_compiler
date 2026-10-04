param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
if(-not [Environment]::Is64BitOperatingSystem -or [Environment]::Is64BitProcess){throw '32-bit Windows PowerShell required'}
$doc=Get-Content -LiteralPath $Source -Raw -Encoding UTF8 | ConvertFrom-Json
if($doc.table -cne 'Station' -or ($doc.columns -join ',') -cne 'STID,DESCR,QTY,TYPE' -or
   @($doc.rows).Count -ne 1 -or $doc.rows[0][0] -cne 'BASE-01' -or
   $doc.rows[0][1] -cne 'ODBC merged teaching base' -or $null -ne $doc.rows[0][2] -or
   $null -ne $doc.rows[0][3]){throw 'frozen Station patch differs'}
if(Test-Path -LiteralPath $Output){throw 'MDB output exists'}
$catalog=New-Object -ComObject ADOX.Catalog
$null=$catalog.Create("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output;Jet OLEDB:Engine Type=5")
$catalog.ActiveConnection.Close();$catalog=$null
$connection=New-Object -ComObject ADODB.Connection
try {
  $connection.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output")
  $affected=0
  $null=$connection.Execute('CREATE TABLE [Station] ([STID] TEXT(255), [DESCR] TEXT(255), [QTY] INTEGER, [TYPE] TEXT(255))',[ref]$affected)
  $null=$connection.Execute("INSERT INTO [Station] ([STID],[DESCR],[QTY],[TYPE]) VALUES ('BASE-01','ODBC merged teaching base',NULL,NULL)",[ref]$affected)
} finally {if($connection.State -eq 1){$connection.Close()}}
$odbc=[System.Data.Odbc.OdbcConnection]::new("Driver={Microsoft Access Driver (*.mdb)};DBQ=$Output;ReadOnly=1;")
try {
  $odbc.Open()
  $tables=@($odbc.GetSchema('Tables').Rows | Where-Object {$_['TABLE_TYPE'] -eq 'TABLE' -and $_['TABLE_NAME'] -notlike 'MSys*'} | ForEach-Object {[string]$_['TABLE_NAME']})
  if($tables.Count -ne 1 -or $tables[0] -cne 'Station'){throw 'unexpected MDB user tables'}
  $cmd=$odbc.CreateCommand();$cmd.CommandText='SELECT [STID],[DESCR],[QTY],[TYPE] FROM [Station] ORDER BY [STID]'
  $reader=$cmd.ExecuteReader();$rows=@()
  while($reader.Read()){$rows+=,@($reader.GetString(0),$reader.GetString(1),$(if($reader.IsDBNull(2)){$null}else{$reader.GetInt32(2)}),$(if($reader.IsDBNull(3)){$null}else{$reader.GetString(3)}))}
  $reader.Close()
  if($rows.Count -ne 1 -or ($rows[0][0..1] -join '|') -cne 'BASE-01|ODBC merged teaching base' -or
     $null -ne $rows[0][2] -or $null -ne $rows[0][3]){throw 'MDB readback differs'}
  [ordered]@{schema='simlox-k05-var02-mdb-readback/v1';process_bitness=32;driver='Microsoft Access Driver (*.mdb)';tables=$tables;columns=@('STID','DESCR','QTY','TYPE');rows=$rows;database_bytes=(Get-Item -LiteralPath $Output).Length;database_sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($Output,'.readback.json')) -Encoding UTF8
} finally {$odbc.Close()}
