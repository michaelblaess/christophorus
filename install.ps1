# ============================================================
#  Christophorus - installer for Windows (PowerShell)
#
#  Usage:
#    irm https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.ps1 | iex
#
#  Downloads the prebuilt Windows package of the latest release.
#  No Python and no git required.
#
#  Installs to:  %LOCALAPPDATA%\christophorus\
#  Commands:     christophorus, christo (added to the user PATH)
#
#  Optional environment variables (mainly for testing):
#    CHRISTOPHORUS_INSTALL_DIR  other install folder
#    CHRISTOPHORUS_NO_PATH=1    do not touch the user PATH
# ============================================================

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = "michaelblaess/christophorus"
$InstallDir = if ($env:CHRISTOPHORUS_INSTALL_DIR) { $env:CHRISTOPHORUS_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "christophorus" }
$AppDir = Join-Path $InstallDir "app"
$BinDir = Join-Path $InstallDir "bin"

Write-Host ""
Write-Host "  Christophorus - installer" -ForegroundColor Cyan
Write-Host ""

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-Host "  [ERROR] Only 64-bit Windows is supported." -ForegroundColor Red
    exit 1
}

# --- Latest release ---
Write-Host "  Looking up the latest release..."
$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -UseBasicParsing
$Version = $Release.tag_name
$Asset = $Release.assets | Where-Object { $_.name -like "*-win64.zip" } | Select-Object -First 1
if (-not $Asset) {
    Write-Host "  [ERROR] Release $Version has no Windows package." -ForegroundColor Red
    Write-Host "  See https://github.com/$Repo/releases"
    exit 1
}
Write-Host "  [OK] $Version ($($Asset.name))" -ForegroundColor Green

# --- Download and unpack ---
$TmpDir = Join-Path $env:TEMP "christophorus-install"
if (Test-Path $TmpDir) { Remove-Item -Recurse -Force $TmpDir }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
$ZipFile = Join-Path $TmpDir $Asset.name

Write-Host "  Downloading..."
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ZipFile -UseBasicParsing
Expand-Archive -Path $ZipFile -DestinationPath $TmpDir -Force

$Exe = Get-ChildItem -Path $TmpDir -Recurse -Filter "christophorus.exe" | Select-Object -First 1
if (-not $Exe) {
    Write-Host "  [ERROR] christophorus.exe not found in the package." -ForegroundColor Red
    exit 1
}

# Replace only the program files. Settings and logbooks live elsewhere
# (~\.christo and the folders you chose) and are not touched.
if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Move-Item -Path $Exe.Directory.FullName -Destination $AppDir
Remove-Item -Recurse -Force $TmpDir
Write-Host "  [OK] Installed to $AppDir" -ForegroundColor Green

# --- Commands ---
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
$Target = Join-Path $AppDir "christophorus.exe"
foreach ($Name in @("christophorus", "christo")) {
    $Content = "@echo off`r`n`"$Target`" %*`r`n"
    [IO.File]::WriteAllText((Join-Path $BinDir "$Name.cmd"), $Content, [Text.Encoding]::ASCII)
}
Write-Host "  [OK] Commands christophorus and christo created" -ForegroundColor Green

# --- PATH ---
if ($env:CHRISTOPHORUS_NO_PATH -ne "1") {
    $UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $UserPath) { $UserPath = "" }
    if (($UserPath -split ";") -notcontains $BinDir) {
        [Environment]::SetEnvironmentVariable("Path", "$BinDir;$UserPath", "User")
        Write-Host "  [OK] Added to your PATH: $BinDir" -ForegroundColor Green
        Write-Host "  Open a new terminal so the PATH takes effect." -ForegroundColor Yellow
    }
    $env:Path = "$BinDir;$env:Path"
}

Write-Host ""
Write-Host "  Done: Christophorus $Version" -ForegroundColor Green
Write-Host ""
Write-Host "  Start:      christophorus   (or: christo)"
Write-Host "  Update:     run this installer again"
Write-Host "  Uninstall:  Remove-Item -Recurse '$InstallDir'" -ForegroundColor Gray
Write-Host ""
