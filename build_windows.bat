@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found. Install Python 3.11 and check "Add to PATH".
    goto :err
)

echo Checking Python version...
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.11 or newer is required. Got:
    python --version
    goto :err
)

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :err
python -m pip install -r backend\requirements-desktop.txt
if errorlevel 1 goto :err

echo Closing any running Zelvera instance...
taskkill /f /im Zelvera.exe >nul 2>nul

echo [2/4] Building executable (may take 5-10 minutes)...
pyinstaller --clean --noconfirm zelvera.spec
if errorlevel 1 goto :err

echo [3/4] Checking result...
if not exist "dist\Zelvera\Zelvera.exe" (
    echo [ERROR] dist\Zelvera\Zelvera.exe not found.
    goto :err
)

echo.
echo [DONE] Application built:
echo   dist\Zelvera\Zelvera.exe
echo.
echo Run it by double-clicking Zelvera.exe.
echo Data is stored locally in %USERPROFILE%\zelvera-data.
if /i "%CI%"=="true" exit /b 0
pause
exit /b 0

:err
echo.
echo [ERROR] Build failed. See messages above.
if /i "%CI%"=="true" exit /b 1
pause
exit /b 1
