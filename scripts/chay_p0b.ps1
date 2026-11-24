# Start the disposable baseline server and capture UI evidence in one process session.
# Prerequisite: ../sim-v0-goc is v0-goc, its venv/dependencies/database are ready,
# and scripts/p0b_seed.py has run once against the fresh database.
$ErrorActionPreference = 'Stop'
$p0bRepo = Split-Path -Parent $PSScriptRoot
$p0bWorktree = Join-Path (Split-Path -Parent $p0bRepo) 'sim-v0-goc'
$p0bPython = Join-Path $p0bWorktree 'venv\Scripts\python.exe'
$p0bTemp = Join-Path (Split-Path -Parent (Split-Path -Parent $p0bRepo)) 'tmp'
$env:SECRET_KEY = 'dev-evidence'
$env:PYTHONUTF8 = '1'
$env:BASE_URL = 'http://127.0.0.1:8001'
$env:P0B_WORKTREE = $p0bWorktree
if (-not $env:PLAYWRIGHT_BROWSERS_PATH) {
    $env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $p0bTemp 'playwright-browsers'
}
$p0bProcess = Start-Process -FilePath $p0bPython -ArgumentList @(
    '-u', 'manage.py', 'runserver', '127.0.0.1:8001', '--noreload'
) -WorkingDirectory $p0bWorktree -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $p0bTemp 'p0b-server.stdout.txt') `
    -RedirectStandardError (Join-Path $p0bTemp 'p0b-server.stderr.txt')
try {
    $p0bReady = $false
    for ($p0bAttempt = 0; $p0bAttempt -lt 20; $p0bAttempt++) {
        if ($p0bProcess.HasExited) { throw 'Demo server exited before capture' }
        try {
            $p0bResponse = Invoke-WebRequest "$env:BASE_URL/accounts/login/" -UseBasicParsing -TimeoutSec 2
            if ($p0bResponse.StatusCode -eq 200) { $p0bReady = $true; break }
        } catch { Start-Sleep -Milliseconds 250 }
    }
    if (-not $p0bReady) { throw 'Demo server did not return login HTTP 200' }
    Write-Output 'LOGIN_HTTP=200'
    & $p0bPython (Join-Path $PSScriptRoot 'chup_bang_chung_truoc.py')
    if ($LASTEXITCODE -ne 0) { throw "Capture exit $LASTEXITCODE" }
} finally {
    if (-not $p0bProcess.HasExited) { Stop-Process -Id $p0bProcess.Id }
}
