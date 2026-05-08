param(
    [string]$RepoName = "opengesture-vision-control",
    [string]$Description = "OPENGESTURE: laptop camera AI gesture, face, voice and body controller with LAN mobile app.",
    [ValidateSet("public", "private")]
    [string]$Visibility = "public"
)

$ErrorActionPreference = "Stop"

function Get-PlainToken {
    if ($env:GITHUB_TOKEN) {
        return $env:GITHUB_TOKEN
    }
    Write-Host "Pega un GitHub Personal Access Token con permiso repo. No se guarda en disco." -ForegroundColor Cyan
    $secure = Read-Host "GitHub token" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Invoke-GitHub {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null
    )
    $params = @{
        Method = $Method
        Uri = $Uri
        Headers = $script:Headers
        ContentType = "application/json"
    }
    if ($null -ne $Body) {
        $params.Body = ($Body | ConvertTo-Json -Depth 20)
    }
    Invoke-RestMethod @params
}

function Should-SkipFile {
    param([string]$RelativePath)
    $path = $RelativePath -replace "\\", "/"
    if ($path -like ".venv/*") { return $true }
    if ($path -like ".git/*") { return $true }
    if ($path -like "logs/*") { return $true }
    if ($path -like "__pycache__/*") { return $true }
    if ($path -like "*/__pycache__/*") { return $true }
    if ($path -eq "config/gesture_config.json") { return $true }
    if ($path -eq "config/latest_frame.jpg") { return $true }
    if ($path -eq "config/runtime_state.json") { return $true }
    if ($path -eq "config/visualizer.pid") { return $true }
    return $false
}

function Get-RelativePath {
    param(
        [string]$RootPath,
        [string]$FilePath
    )
    $rootFull = [IO.Path]::GetFullPath($RootPath).TrimEnd("\", "/")
    $fileFull = [IO.Path]::GetFullPath($FilePath)
    if ($fileFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        return $fileFull.Substring($rootFull.Length).TrimStart("\", "/")
    }
    return Split-Path -Leaf $fileFull
}

$token = Get-PlainToken
$script:Headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$user = Invoke-GitHub -Method "GET" -Uri "https://api.github.com/user"
$owner = $user.login
$private = $Visibility -eq "private"
$repoUrl = "https://github.com/$owner/$RepoName"

try {
    Invoke-GitHub -Method "POST" -Uri "https://api.github.com/user/repos" -Body @{
        name = $RepoName
        description = $Description
        private = $private
        auto_init = $false
    } | Out-Null
    Write-Host "Repo creado: $repoUrl" -ForegroundColor Green
}
catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 422) {
        Write-Host "El repo ya existe, voy a actualizar archivos: $repoUrl" -ForegroundColor Yellow
    }
    else {
        throw
    }
}

$root = (Get-Location).Path
$files = Get-ChildItem -Path $root -Recurse -File |
    Where-Object {
        $relative = Get-RelativePath -RootPath $root -FilePath $_.FullName
        -not (Should-SkipFile $relative)
    } |
    Sort-Object FullName

foreach ($file in $files) {
    $relative = (Get-RelativePath -RootPath $root -FilePath $file.FullName) -replace "\\", "/"
    $encodedPath = [uri]::EscapeDataString($relative).Replace("%2F", "/")
    $content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file.FullName))
    $body = @{
        message = "Add $relative"
        content = $content
    }

    try {
        $existing = Invoke-GitHub -Method "GET" -Uri "https://api.github.com/repos/$owner/$RepoName/contents/$encodedPath"
        if ($existing.sha) {
            $body.sha = $existing.sha
            $body.message = "Update $relative"
        }
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 404) {
            throw
        }
    }

    Invoke-GitHub -Method "PUT" -Uri "https://api.github.com/repos/$owner/$RepoName/contents/$encodedPath" -Body $body | Out-Null
    Write-Host "Subido $relative"
}

Write-Host ""
Write-Host "Listo: $repoUrl" -ForegroundColor Green
