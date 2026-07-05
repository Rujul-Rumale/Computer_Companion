@echo off
:: AI Companion - Windows Setup Script
:: Run: setup.bat
:: Prerequisites: Python 3.11+

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo  AI Companion - Setup
echo ============================================
echo.

:: --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ required.
    python --version
    pause
    exit /b 1
)
echo [OK] Python found.

:: --- Check pip ---
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found.
    pause
    exit /b 1
)
echo [OK] pip found.
echo.

:: --- Create directories ---
if not exist "data" mkdir data
if not exist "logs" mkdir logs
echo [OK] data/ and logs/ directories ready.

:: --- Create config.yaml from example ---
if not exist "config\config.yaml" (
    if exist "config\config.example.yaml" (
        copy "config\config.example.yaml" "config\config.yaml" >nul
        echo [OK] Created config\config.yaml from example.
        echo      Edit this file to set your model path and location.
    ) else (
        echo [WARNING] No config.example.yaml found. Create config\config.yaml manually.
    )
) else (
    echo [OK] config\config.yaml already exists.
)
echo.

:: --- Install dependencies ---
echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] pip install had issues. Check output above.
)
echo.

:: --- Setup complete ---
echo ============================================
echo  Setup Complete
echo ============================================
echo.
echo BEFORE STARTING:
echo  1. Download a GGUF model (e.g. from Hugging Face)
echo  2. Edit config/config.yaml:
echo       - Set llama_model_path to your GGUF file
echo       - Update user: section with your location
echo.
echo TO START:
echo  launch_companion.bat
echo.
echo HOTKEYS:
echo  Ctrl+Space     - Push to talk (hold)
echo  Ctrl+Shift+J   - Screenshot + analyze
echo  Enter          - Send text message
echo.
pause
