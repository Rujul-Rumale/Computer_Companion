$ErrorActionPreference = "Stop"

Set-StrictMode -Version Latest
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$StartupLog = Join-Path $LogDir "startup.log"
$ErrorLog = Join-Path $LogDir "error.log"

function Write-Log {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] $Message"
    Add-Content -Path $StartupLog -Value $line
    Write-Host $line
}

function Write-Err {
    param([string]$Message)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$stamp] ERROR: $Message"
    Add-Content -Path $ErrorLog -Value $line
    Write-Host $line -ForegroundColor Red
}

function Find-Python {
    $candidates = @(
        Join-Path $Root ".venv\Scripts\python.exe",
        "py -3",
        "python"
    )
    foreach ($c in $candidates) {
        if ($c -is [string] -and (Test-Path $c)) { return $c }
    }
    return "py -3"
}

function Invoke-CommandLine {
    param([string]$CommandLine, [string]$Arguments)
    if ($CommandLine -eq "py -3") {
        & py -3 $Arguments
    }
    elseif ($CommandLine -eq "python") {
        & python $Arguments
    }
    else {
        & $CommandLine $Arguments
    }
}

function Test-LmStudioApi {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri "http://127.0.0.1:1234/v1/models"
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Start-LmStudio {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\LM Studio\LM Studio.exe",
        "$env:LOCALAPPDATA\LM Studio\LM Studio.exe",
        "$env:ProgramFiles\LM Studio\LM Studio.exe",
        "$env:ProgramFiles(x86)\LM Studio\LM Studio.exe"
    )

    foreach ($p in $paths) {
        if (Test-Path $p) {
            Write-Log "Starting LM Studio: $p"
            Start-Process -FilePath $p | Out-Null
            return $true
        }
    }

    try {
        $apps = Get-StartApps | Where-Object { $_.Name -like "*LM Studio*" }
        if ($apps) {
            Write-Log "Starting LM Studio from Start menu app entry."
            Start-Process "shell:AppsFolder\$($apps[0].AppID)" | Out-Null
            return $true
        }
    } catch {
        Write-Log "Start menu lookup failed: $($_.Exception.Message)"
    }

    Write-Log "LM Studio executable not found in common paths."
    return $false
}

function Add-CudaToolkitToPath {
    $cudaRoot = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if (-not (Test-Path $cudaRoot)) {
        Write-Log "CUDA Toolkit not found; GPU STT may fall back to CPU."
        return
    }

    $toolkits = Get-ChildItem -Path $cudaRoot -Directory |
        Sort-Object Name -Descending
    foreach ($toolkit in $toolkits) {
        $bin = Join-Path $toolkit.FullName "bin"
        $cublas = Join-Path $bin "cublas64_12.dll"
        if ((Test-Path $bin) -and (Test-Path $cublas)) {
            $env:PATH = "$bin;$env:PATH"
            Write-Log "CUDA Toolkit added to PATH: $bin"
            return
        }
    }

    Write-Log "CUDA Toolkit found, but cublas64_12.dll was not found; GPU STT may fall back to CPU."
}

function Ensure-Piper {
    try {
        $piperRoot = Join-Path $Root "data\piper"
        $piperExe = Join-Path $piperRoot "piper.exe"
        $voiceDir = Join-Path $Root "data\voices"
        $voiceModel = Join-Path $voiceDir "en_US-lessac-medium.onnx"
        $voiceConfig = Join-Path $voiceDir "en_US-lessac-medium.onnx.json"
        $piperZip = Join-Path $LogDir "piper_windows_amd64.zip"
        $voiceOnnxUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true"
        $voiceJsonUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true"
        $piperZipUrl = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"

        New-Item -ItemType Directory -Force -Path $piperRoot | Out-Null
        New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

        if (-not (Test-Path $piperExe)) {
            Write-Log "Downloading Piper Windows build."
            Invoke-WebRequest -UseBasicParsing -Uri $piperZipUrl -OutFile $piperZip
            Expand-Archive -Path $piperZip -DestinationPath $piperRoot -Force
            Remove-Item $piperZip -Force -ErrorAction SilentlyContinue

            if (-not (Test-Path $piperExe)) {
                $foundExe = Get-ChildItem -Path $piperRoot -Filter "piper.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($foundExe) {
                    $piperExe = $foundExe.FullName
                }
            }
        }

        if (-not (Test-Path $voiceModel)) {
            Write-Log "Downloading Piper voice model: en_US-lessac-medium."
            Invoke-WebRequest -UseBasicParsing -Uri $voiceOnnxUrl -OutFile $voiceModel
        }

        if (-not (Test-Path $voiceConfig)) {
            Write-Log "Downloading Piper voice config: en_US-lessac-medium."
            Invoke-WebRequest -UseBasicParsing -Uri $voiceJsonUrl -OutFile $voiceConfig
        }

        if (Test-Path $piperExe) {
            $env:PATH = "$(Split-Path -Parent $piperExe);$env:PATH"
            $env:PIPER_EXE = $piperExe
            Write-Log "Piper prepared: $piperExe"
        } else {
            Write-Log "Piper download finished, but piper.exe was not found in $piperRoot."
        }
    } catch {
        Write-Log "Piper setup failed: $($_.Exception.Message)"
    }
}

try {
    Write-Log "Launcher started."

    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Log "Creating virtual environment."
        $py = (Get-Command py -ErrorAction SilentlyContinue)
        if ($py) {
            & py -3 -m venv .venv | Out-Null
        } else {
            & python -m venv .venv | Out-Null
        }
        if (-not (Test-Path $venvPython)) {
            throw "Failed to create virtual environment."
        }
    }

    Write-Log "Ensuring pip is current."
    & $venvPython -m pip install --upgrade pip | Out-Null

    Write-Log "Installing requirements."
    & $venvPython -m pip install -r requirements.txt | Out-Null

    Add-CudaToolkitToPath
    Ensure-Piper

    if (-not (Test-Path "data")) {
        New-Item -ItemType Directory -Force -Path "data" | Out-Null
    }

    if (-not (Test-Path "data\memory.db")) {
        Write-Log "Seeding memory database."
        & $venvPython seed_memory.py | Out-Null
    }

    if (-not (Test-LmStudioApi)) {
        Write-Log "LM Studio API is not reachable."
        $started = Start-LmStudio
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            if (Test-LmStudioApi) { break }
        }
    }

    if (-not (Test-LmStudioApi)) {
        Write-Err "LM Studio API is still unreachable at http://127.0.0.1:1234/v1/models"
        Write-Host ""
        Write-Host "Open LM Studio, load a model, and start the local server on port 1234."
        pause
        exit 2
    }

    try {
        $models = (Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:1234/v1/models").data
        if (-not $models -or $models.Count -eq 0) {
            Write-Err "LM Studio is running, but no model is loaded."
            Write-Host ""
            Write-Host "Please load a model in LM Studio and try again."
            pause
            exit 3
        }
        $first = $models[0].id
        Write-Log "Loaded model detected: $first"
    } catch {
        Write-Err "Failed to inspect LM Studio models: $($_.Exception.Message)"
        pause
        exit 4
    }

    Write-Log "Starting AI Companion."
    & $venvPython main.py
    exit $LASTEXITCODE
}
catch {
    Write-Err $_.Exception.Message
    Write-Host ""
    Write-Host "Startup failed. See logs\startup.log and logs\error.log."
    pause
    exit 1
}
