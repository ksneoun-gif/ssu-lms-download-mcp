param([switch]$FindCliOnly, [switch]$FindGitOnly)
$ErrorActionPreference = 'Stop'
function Find-CodexCli {
    $candidates = @()
    $command = Get-Command codex.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    try {
        foreach ($package in (Get-AppxPackage '*Codex*' -ErrorAction Stop | Sort-Object Version -Descending)) {
            $candidates += Join-Path $package.InstallLocation 'app\resources\codex.exe'
            $candidates += Join-Path $package.InstallLocation 'resources\codex.exe'
        }
    } catch { }
    foreach ($process in (Get-Process -Name Codex -ErrorAction SilentlyContinue)) {
        try {
            if ($process.Path) {
                $appDirectory = Split-Path -Parent $process.Path
                $candidates += Join-Path $appDirectory 'resources\codex.exe'
                $candidates += Join-Path $appDirectory 'app\resources\codex.exe'
            }
        } catch { }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    throw 'Codex CLI could not be located through PATH, installed app packages, or the running Codex app. Keep Codex open and retry in ordinary PowerShell.'
}
function Find-GitExecutable {
    $candidates = @()
    $command = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    $candidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe'
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if ($root) {
            $candidates += Join-Path $root 'Git\cmd\git.exe'
            $candidates += Join-Path $root 'Programs\Git\cmd\git.exe'
        }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            $null = & $candidate --version
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { }
    }
    throw 'A working git.exe was not found in PATH, the Codex runtime, or standard Git installations.'
}
$gitPath = Find-GitExecutable
$env:PATH = (Split-Path -Parent $gitPath) + [IO.Path]::PathSeparator + $env:PATH
Write-Host "GIT_FOUND: $gitPath"
if ($FindGitOnly) { return }
$codexPath = Find-CodexCli
Write-Host "CODEX_CLI_FOUND: $codexPath"
if ($FindCliOnly) { return }
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
