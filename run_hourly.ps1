param(
    [switch]$CoreOnly
)

$ErrorActionPreference = "Continue"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$logDirectory = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd-HHmmss"
$logFile = Join-Path $logDirectory "scan-$timestamp.log"
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $logFile,
    ("--- Scan started {0:O} ---`r`n" -f (Get-Date)),
    $utf8
)

$env:PYTHONIOENCODING = "utf-8"
$scriptPath = Join-Path $PSScriptRoot "main.py"
$scannerArguments = if ($CoreOnly) { " --core-only" } else { "" }
$command = "python `"$scriptPath`"$scannerArguments >> `"$logFile`" 2>&1"
& $env:ComSpec /d /c $command
$exitCode = $LASTEXITCODE
[System.IO.File]::AppendAllText(
    $logFile,
    ("--- Scan finished with exit code {0} ---`r`n" -f $exitCode),
    $utf8
)
exit $exitCode
