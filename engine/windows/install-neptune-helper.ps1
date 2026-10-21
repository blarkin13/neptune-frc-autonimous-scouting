# Neptune Helper installer for Windows 10/11 (64-bit x86). Per-user; no administrator rights needed.
# Checks each prerequisite first and installs only what is missing:
#   Python 3.11+ with Tk (installs the official python.org 3.13.16 per user if none is found)
#   FFmpeg/FFprobe (pinned gyan.dev 9.0.2 essentials build), Deno (yt-dlp's YouTube JavaScript runtime)
#   Private Python environment with hash-locked RapidOCR, ONNX Runtime and yt-dlp wheels
# Every download is checked against the SHA-256 in requirements.json before use.
# Then runs the helper's self-check and creates Start menu and Desktop shortcuts.
# Uninstall: run this script with -Uninstall (keeps saved match work in %USERPROFILE%\.neptune-helper).
param([switch]$Uninstall, [switch]$NoShortcuts)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Package = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppSource = Join-Path $Package 'app'
$Home_ = Join-Path $env:LOCALAPPDATA 'Neptune Helper'
$Tools = Join-Path $Home_ 'tools\bin'
$Downloads = Join-Path $Home_ 'downloads'
$PrivatePython = Join-Path $Home_ 'python'
$Venv = Join-Path $Home_ 'python-environment'
$App = Join-Path $Home_ 'app'
$StartMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Neptune Helper.lnk'
$Desktop = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Neptune Helper.lnk'

function Step($text) { Write-Host "`n$text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Fail($text) { Write-Host "`n  $text" -ForegroundColor Red; exit 1 }

if ($Uninstall) {
    Step 'Removing Neptune Helper (saved match work in %USERPROFILE%\.neptune-helper is kept)'
    foreach ($p in @($StartMenu, $Desktop)) { if (Test-Path $p) { Remove-Item $p -Force } }
    if (Test-Path $Home_) { Remove-Item $Home_ -Recurse -Force }
    Ok 'Removed shortcuts, private Python environment, tools and app files.'
    exit 0
}

$Requirements = Get-Content (Join-Path $AppSource 'requirements.json') -Raw | ConvertFrom-Json
function Requirement($id) { $Requirements.requirements | Where-Object { $_.id -eq $id } | Select-Object -First 1 }

function Get-Verified($url, $sha256, $name) {
    New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
    $target = Join-Path $Downloads $name
    if ((Test-Path $target) -and ((Get-FileHash $target -Algorithm SHA256).Hash -eq $sha256.ToUpper())) { return $target }
    if (-not $url.StartsWith('https://')) { Fail "Refusing a non-HTTPS download: $url" }
    Write-Host "  Downloading $name ..."
    $partial = "$target.partial"
    Invoke-WebRequest -Uri $url -OutFile $partial -UseBasicParsing
    $actual = (Get-FileHash $partial -Algorithm SHA256).Hash
    if ($actual -ne $sha256.ToUpper()) { Remove-Item $partial -Force; Fail "$name did not pass its SHA-256 check. Retry setup." }
    Move-Item $partial $target -Force
    return $target
}

function Test-Python($exe) {
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    & $exe -c "import sys, tkinter, venv, ssl; assert sys.version_info >= (3, 11)" 2>$null
    return $LASTEXITCODE -eq 0
}

# ---- 1. This computer -------------------------------------------------------------------------
Step 'Checking this computer'
$arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($arch -ne 'AMD64') { Fail "This installer supports 64-bit x86 Windows only (this computer: $arch). Windows on ARM is not supported." }
$build = [Environment]::OSVersion.Version.Build
if ($build -lt 17763) { Fail 'Neptune Helper needs Windows 10 version 1809 or newer, or Windows 11.' }
$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($env:LOCALAPPDATA).Substring(0, 1))
if ($drive.Free -lt 3GB) { Fail 'Free at least 3 GB of disk space, then retry.' }
Ok "Windows build $build, $arch, $([math]::Round($drive.Free / 1GB, 1)) GB free"

# ---- 2. Package integrity ---------------------------------------------------------------------
Step 'Verifying the downloaded package'
$manifest = Get-Content (Join-Path $Package 'files.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.PSObject.Properties) {
    $path = Join-Path $Package $entry.Name
    if (-not (Test-Path $path) -or (Get-FileHash $path -Algorithm SHA256).Hash -ne $entry.Value.ToUpper()) {
        Fail "A setup file is missing or changed: $($entry.Name). Download and unzip Neptune Helper again."
    }
}
Ok 'All package files match their checksums'

# ---- 3. Python ----------------------------------------------------------------------------------
Step 'Checking Python 3.11+ with window support'
$python = $null
foreach ($candidate in @((Join-Path $PrivatePython 'python.exe'))) { if (Test-Python $candidate) { $python = $candidate } }
if (-not $python -and (Get-Command py.exe -ErrorAction SilentlyContinue)) {
    foreach ($v in @('3.13', '3.12', '3.11')) {
        $found = & py.exe "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and (Test-Python $found)) { $python = $found; break }
    }
}
if (-not $python) {
    $req = Requirement 'windows_python'
    $installer = Get-Verified $req.source $req.sha256 'python-installer.exe'
    $signature = Get-AuthenticodeSignature $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { Fail 'The Python installer signature is not valid.' }
    Write-Host '  Installing Python for this user (no administrator rights needed) ...'
    $args_ = @('/quiet', 'InstallAllUsers=0', "TargetDir=$PrivatePython", 'Include_launcher=0', 'Include_test=0', 'Include_tcltk=1',
               'Include_pip=1', 'PrependPath=0', 'Shortcuts=0', 'AssociateFiles=0', 'CompileAll=0')
    $p = Start-Process -FilePath $installer -ArgumentList $args_ -Wait -PassThru
    if ($p.ExitCode -ne 0) { Fail "The Python installer stopped (code $($p.ExitCode)). Retry setup." }
    $python = Join-Path $PrivatePython 'python.exe'
    if (-not (Test-Python $python)) { Fail 'Python was installed but window support (Tk) is missing.' }
}
Ok "Python: $python"

# ---- 4. FFmpeg ----------------------------------------------------------------------------------
Step 'Checking FFmpeg'
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
function Test-Tool($exe, $arg) { if (-not $exe) { return $false }; & $exe $arg *> $null; return $LASTEXITCODE -eq 0 }
$ffmpeg = Join-Path $Tools 'ffmpeg.exe'
if (-not ((Test-Tool $ffmpeg '-version') -and (Test-Tool (Join-Path $Tools 'ffprobe.exe') '-version'))) {
    $onPath = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if ($onPath -and (Get-Command ffprobe.exe -ErrorAction SilentlyContinue) -and (Test-Tool $onPath.Source '-version')) {
        Ok "Using the installed FFmpeg: $($onPath.Source)"
    } else {
        $req = Requirement 'windows_ffmpeg'
        $zip = Get-Verified $req.source $req.sha256 'ffmpeg.zip'
        $unpack = Join-Path $Downloads 'ffmpeg-unpacked'
        if (Test-Path $unpack) { Remove-Item $unpack -Recurse -Force }
        Expand-Archive -Path $zip -DestinationPath $unpack
        foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
            $file = Get-ChildItem -Path $unpack -Recurse -Filter $name | Select-Object -First 1
            if (-not $file) { Fail "$name was not found in the FFmpeg download." }
            Copy-Item $file.FullName (Join-Path $Tools $name) -Force
        }
        $license = Get-ChildItem -Path $unpack -Recurse -Filter 'LICENSE*' | Select-Object -First 1
        if ($license) { Copy-Item $license.FullName (Join-Path $Tools 'FFMPEG-LICENSE.txt') -Force }
        Remove-Item $unpack -Recurse -Force
        if (-not (Test-Tool $ffmpeg '-version')) { Fail 'FFmpeg was installed but does not run.' }
        Ok "Installed FFmpeg $($req.version)"
    }
} else { Ok 'FFmpeg already installed' }

# ---- 5. YouTube JavaScript runtime (Deno) ------------------------------------------------------
Step 'Checking the YouTube video runtime'
$deno = Join-Path $Tools 'deno.exe'
if (Test-Tool $deno '--version') { Ok 'Deno already installed' }
elseif ((Get-Command deno.exe -ErrorAction SilentlyContinue) -or (Get-Command node.exe -ErrorAction SilentlyContinue)) { Ok 'Using the installed Deno or Node.js' }
else {
    $req = Requirement 'deno'
    $src = $req.sources.'windows-x86_64'
    $zip = Get-Verified $src[0] $src[1] 'deno.zip'
    Expand-Archive -Path $zip -DestinationPath $Tools -Force
    if (-not (Test-Tool $deno '--version')) { Fail 'Deno was installed but does not run.' }
    Ok "Installed Deno $($req.version)"
}

# ---- 6. App files and private Python environment ----------------------------------------------
Step 'Installing Neptune Helper and its text reader'
if (Test-Path $App) { Remove-Item $App -Recurse -Force }
Copy-Item $AppSource $App -Recurse
$venvPython = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Python $venvPython)) {
    if (Test-Path $Venv) { Remove-Item $Venv -Recurse -Force }
    & $python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail 'Could not create the private Python environment.' }
}
$check = "from importlib.metadata import version as v; assert v('rapidocr')=='3.10.0' and v('onnxruntime')=='1.31.0' and v('yt-dlp')=='2026.8.19'"
& $venvPython -c $check 2>$null
if ($LASTEXITCODE -ne 0) {
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    & $venvPython -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r (Join-Path $App 'requirements-ocr.txt')
    if ($LASTEXITCODE -ne 0) { Fail 'Python packages could not be installed. Check the internet connection and retry.' }
}
Ok 'RapidOCR, ONNX Runtime and video download support installed'

# ---- 7. Self-check ------------------------------------------------------------------------------
Step 'Running the helper self-check'
& $venvPython (Join-Path $App 'neptune_app.py') --check
if ($LASTEXITCODE -ne 0) { Fail 'The self-check failed. Share the messages above with the Neptune owner.' }

# ---- 8. Shortcuts --------------------------------------------------------------------------------
if (-not $NoShortcuts) {
    Step 'Creating shortcuts'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($path in @($StartMenu, $Desktop)) {
        $link = $shell.CreateShortcut($path)
        $link.TargetPath = Join-Path $Venv 'Scripts\pythonw.exe'
        $link.Arguments = '"' + (Join-Path $App 'neptune_app.py') + '"'
        $link.WorkingDirectory = $App
        $link.Description = 'Neptune Helper: analyse FRC match videos on this computer'
        $link.IconLocation = (Join-Path $Venv 'Scripts\pythonw.exe') + ',0'
        $link.Save()
    }
    Ok 'Start menu and Desktop shortcuts: Neptune Helper'
}

Write-Host "`nNeptune Helper is installed. Open it from the Start menu or Desktop shortcut." -ForegroundColor Green
Write-Host 'Run this installer again at any time; it only installs what is missing.'
exit 0
