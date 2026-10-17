param([switch]$Setup, [switch]$Check, [switch]$Configure)
$ErrorActionPreference = 'Stop'
$candidates = @()
if ($env:SSU_LMS_PYTHON) { $candidates += $env:SSU_LMS_PYTHON }
if ($env:SSU_LMS_ENV) { $candidates += Join-Path $env:SSU_LMS_ENV 'Scripts\python.exe' }
$candidates += Join-Path $PSScriptRoot '.runtime\Scripts\python.exe'
$candidates += Join-Path $PSScriptRoot '..\..\.runtime\Scripts\python.exe'
$candidates += Join-Path $env:LOCALAPPDATA 'ssu-lms-download-mcp\venv\Scripts\python.exe'
$candidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$candidates += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
$candidates += Get-Command python.exe,python3.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if ($candidate -match '[\\/]WindowsApps[\\/]' -or -not (Test-Path -LiteralPath $candidate)) { continue }
    try {
        & $candidate -I -c 'import sys;sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)' 2>$null
        if ($LASTEXITCODE -ne 0) { continue }
    } catch { continue }
    $arguments = @((Join-Path $PSScriptRoot 'bootstrap.py'))
    if ($Setup) { $arguments += '--setup' }
    if ($Check -or $Configure) { $arguments += '--check' }
    & $candidate @arguments
    if ($LASTEXITCODE -ne 0 -or -not $Configure) { exit $LASTEXITCODE }
    # Bootstrap may have created a venv; configure with that interpreter rather than base Python.
    $environment = if ($env:SSU_LMS_ENV) { $env:SSU_LMS_ENV } else { Join-Path $env:LOCALAPPDATA 'ssu-lms-download-mcp\venv' }
    $python = Join-Path $environment 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python = $candidate }
    & $python (Join-Path $PSScriptRoot 'install_windows.py') --configure
    exit $LASTEXITCODE
}
[Console]::Error.WriteLine('Install 64-bit Python 3.10-3.13 or set SSU_LMS_PYTHON to python.exe.')
exit 1
