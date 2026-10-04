param(
  [Parameter(Mandatory=$true)][ValidateSet('control','key_level1','key_level2')][string]$Kind,
  [Parameter(Mandatory=$true)][string]$Source,
  [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
if(-not [Environment]::Is64BitOperatingSystem -or [Environment]::Is64BitProcess){throw '32-bit Windows PowerShell required'}
$doc=Get-Content -LiteralPath $Source -Raw -Encoding UTF8 | ConvertFrom-Json
$expectedNames=switch($Kind){'control'{@('Control','Station')} 'key_level1'{@('IncludeFiles','Station')} 'key_level2'{@('Station')}}
$tables=@($doc.tables)
$names=@($tables | ForEach-Object {$_.table})
if(($names -join ',') -cne ($expectedNames -join ',') -or $tables.Count -ne $expectedNames.Count){throw 'MDB source table set differs'}
if(Test-Path -LiteralPath $Output){throw 'database output already exists'}
function Sql-Type([string]$table,[string]$name,$value) {
  if($table -eq 'IncludeFiles' -and $name -eq 'NOTE'){return 'MEMO'}
  if($null -eq $value){return 'TEXT(255)'}
  if($value -is [int] -or $value -is [long]){return 'INTEGER'}
  if($value -is [double] -or $value -is [decimal]){return 'DOUBLE'}
  return 'TEXT(255)'
}
function Sql-Value($value) {
  if($null -eq $value){return 'NULL'}
  if($value -is [bool]){throw 'boolean source cell unsupported'}
  if($value -is [string]){return "'" + $value.Replace("'","''") + "'"}
  return [Convert]::ToString($value,[Globalization.CultureInfo]::InvariantCulture)
}
foreach($table in $tables) {
  if(@($table.rows).Count -ne 1 -or @($table.columns).Count -ne @($table.rows[0]).Count){throw "expected one complete row in $($table.table)"}
  if(@($table.columns | Select-Object -Unique).Count -ne @($table.columns).Count){throw "duplicate column in $($table.table)"}
}
if($Kind -eq 'control') {
  $control=@($tables | Where-Object {$_.table -eq 'Control'})[0]
  if(@($control.columns).Count -ne 24 -or $control.rows[0][0] -ne 1 -or $control.rows[0][1] -ne 36 -or $control.rows[0][2] -ne '1'){throw 'full Control row differs'}
}
if($Kind -eq 'key_level1') {
  $include=@($tables | Where-Object {$_.table -eq 'IncludeFiles'})[0]
  if($include.rows[0][0] -cne (Join-Path (Split-Path $Output -Parent) 'key-level2.mdb')){throw 'nested key pointer differs'}
}
foreach($table in $tables) {
  if($table.table -eq 'Station' -and ($table.rows[0][0] -ne 'BASE-01' -or $table.rows[0][2] -ne 1 -or $table.rows[0][3] -ne 'WS')){throw 'BASE-01 Station row differs'}
}
$catalog=New-Object -ComObject ADOX.Catalog
$null=$catalog.Create("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output;Jet OLEDB:Engine Type=5")
$catalog.ActiveConnection.Close(); $catalog=$null
$connection=New-Object -ComObject ADODB.Connection
try {
  $connection.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$Output")
  foreach($table in $tables) {
    $columns=@($table.columns)
    $row=@($table.rows[0])
    $definitions=for($i=0;$i -lt $columns.Count;$i++){"[$($columns[$i])] $(Sql-Type $table.table $columns[$i] $row[$i])"}
    $affected=0
    $null=$connection.Execute("CREATE TABLE [$($table.table)] ("+($definitions -join ',')+")",[ref]$affected)
    $fieldList=($columns | ForEach-Object {"[$_]"}) -join ','
    $valueList=($row | ForEach-Object {Sql-Value $_}) -join ','
    $null=$connection.Execute("INSERT INTO [$($table.table)] ($fieldList) VALUES ($valueList)",[ref]$affected)
  }
} finally {if($connection.State -eq 1){$connection.Close()}}
$odbc=[System.Data.Odbc.OdbcConnection]::new("Driver={Microsoft Access Driver (*.mdb)};DBQ=$Output;ReadOnly=1;")
try {
  $odbc.Open()
  $userNames=@($odbc.GetSchema('Tables').Rows | Where-Object {$_['TABLE_TYPE'] -eq 'TABLE'} | ForEach-Object {[string]$_['TABLE_NAME']} | Sort-Object)
  if(($userNames -join ',') -cne (@($expectedNames | Sort-Object) -join ',')){throw 'ODBC user tables differ'}
  $readback=[ordered]@{}
  foreach($table in $tables) {
    $columns=@($table.columns)
    $command=$odbc.CreateCommand()
    $command.CommandText="SELECT "+(($columns | ForEach-Object {"[$_]"}) -join ',')+" FROM [$($table.table)]"
    $reader=$command.ExecuteReader()
    $rows=@()
    while($reader.Read()) {
      $one=@()
      for($i=0;$i -lt $columns.Count;$i++){ $one += if($reader.IsDBNull($i)){$null}else{$reader.GetValue($i)} }
      $rows += ,$one
    }
    $reader.Close()
    if($rows.Count -ne 1){throw "ODBC row count differs: $($table.table)"}
    $readback[$table.table]=[ordered]@{columns=$columns;rows=$rows}
  }
  [ordered]@{schema='simlox-k04-var04-mdb-readback/v1';kind=$Kind;driver='Microsoft Access Driver (*.mdb)';process_bitness=32;tables=$userNames;contents=$readback;database_bytes=(Get-Item -LiteralPath $Output).Length;database_sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()} | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($Output,'.readback.json')) -Encoding UTF8
} finally {$odbc.Close()}
