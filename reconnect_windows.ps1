$ErrorActionPreference = 'Stop'
$codexPath = 'C:\Program Files\WindowsApps\OpenAI.Codex_26.1013.3656.0_x64__2p2nqsd0c76g0\app\resources\codex.exe'
if (-not (Test-Path -LiteralPath $codexPath)) {
    $command = Get-Command codex.exe -ErrorAction SilentlyContinue
    if (-not $command) { throw 'Codex CLI was not found. Open this script on the PC with Codex installed.' }
    $codexPath = $command.Source
}
& $codexPath plugin marketplace upgrade ssu-lms-github
if ($LASTEXITCODE -ne 0) { throw 'Marketplace upgrade failed; the existing installation was retained.' }
& $codexPath plugin add ssu-lms@ssu-lms-github
if ($LASTEXITCODE -ne 0) { throw 'Plugin installation failed.' }
$pluginPath = Join-Path $env:USERPROFILE '.codex\plugins\cache\ssu-lms-github\ssu-lms\0.3.2'
if (-not (Test-Path -LiteralPath (Join-Path $pluginPath 'server.py'))) { throw 'The 0.3.2 plugin was not installed.' }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pluginPath 'start.ps1') -Setup -Configure
if ($LASTEXITCODE -ne 0) { throw 'Python setup or configuration failed.' }
$pythonPath = Join-Path $env:LOCALAPPDATA 'ssu-lms-download-mcp\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'The LMS Python runtime was not found.' }
& $pythonPath (Join-Path $pluginPath 'verify_local.py') --plugin-root $pluginPath
if ($LASTEXITCODE -ne 0) { throw 'Live MCP verification failed. No success is claimed.' }
Write-Host 'SSU_LMS_0.3.2_VERIFIED. Restart Codex to reconnect this conversation.'
