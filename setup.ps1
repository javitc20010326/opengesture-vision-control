$ErrorActionPreference = "Stop"

$pythonPath = where.exe python 2>$null | Select-Object -First 1
if ($LASTEXITCODE -ne 0 -or -not $pythonPath) {
    $localPython = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
    if (Test-Path $localPython) {
        $pythonPath = $localPython
    }
}

if (-not $pythonPath) {
    Write-Host "No encuentro python en PATH." -ForegroundColor Red
    Write-Host "Instala Python 3.10, 3.11 o 3.12 desde https://www.python.org/downloads/windows/"
    Write-Host "Marca Add python.exe to PATH durante la instalacion."
    exit 1
}

& $pythonPath -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Listo. Prueba el visualizador con:" -ForegroundColor Green
Write-Host ".\run.ps1"
Write-Host ""
Write-Host "Cuando reconozca bien la mano, activa control real con:"
Write-Host ".\run.ps1 -Control"
