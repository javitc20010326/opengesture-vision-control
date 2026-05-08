$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"
$bundled = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if ((Test-Path $python) -and -not (& $python -c "pass" 2>$null)) {
    $python = $bundled
}
if (-not (Test-Path $python)) {
    Write-Host "No encuentro Python. Ejecuta setup.ps1 o instala Python 3.12." -ForegroundColor Yellow
    exit 1
}
$sitePackages = Join-Path $PSScriptRoot ".venv\Lib\site-packages"
if (Test-Path $sitePackages) {
    $env:PYTHONPATH = $sitePackages + ";" + $env:PYTHONPATH
}

& $python src\config_web.py
