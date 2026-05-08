$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$launcherShortcutPath = Join-Path $startup "Gesture Visualizer Launcher.lnk"
$configShortcutPath = Join-Path $startup "Gesture Config Web.lnk"
$launcherPath = Join-Path $projectRoot "launcher.ps1"
$configPath = Join-Path $projectRoot "config-server.ps1"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($launcherShortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcherPath`""
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Save()

$configShortcut = $shell.CreateShortcut($configShortcutPath)
$configShortcut.TargetPath = "powershell.exe"
$configShortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$configPath`""
$configShortcut.WorkingDirectory = $projectRoot
$configShortcut.Save()

Write-Host "Instalado en inicio de Windows:" -ForegroundColor Green
Write-Host $launcherShortcutPath
Write-Host $configShortcutPath
Write-Host "En el proximo inicio de sesion, E+R y la web LAN quedaran activos."
