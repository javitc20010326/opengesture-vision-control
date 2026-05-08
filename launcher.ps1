$ErrorActionPreference = "Stop"

$pythonw = ".\.venv\Scripts\pythonw.exe"
$bundled = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe"
if ((Test-Path $pythonw) -and -not (& $pythonw -c "pass" 2>$null)) {
    $pythonw = $bundled
}
if (-not (Test-Path $pythonw)) {
    Write-Host "No encuentro Python. Ejecuta setup.ps1 o instala Python 3.12." -ForegroundColor Yellow
    exit 1
}
$sitePackages = Join-Path $PSScriptRoot ".venv\Lib\site-packages"
if (Test-Path $sitePackages) {
    $env:PYTHONPATH = $sitePackages + ";" + $env:PYTHONPATH
}

Start-Process -FilePath $pythonw -ArgumentList "src\gesture_launcher.py" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
