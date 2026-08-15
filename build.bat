@echo off
echo ============================================
echo   Decipline -- Build Script
echo ============================================

echo [0/3] Closing any running Decipline instance...
taskkill /IM Decipline.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo [1/3] Generating assets...
python generate_assets.py

echo [2/3] Building Decipline.exe...
pyinstaller build.spec --clean --noconfirm

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\Decipline.exe
echo ============================================
pause
