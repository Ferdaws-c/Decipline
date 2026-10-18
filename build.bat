@echo off
setlocal
cd /d "%~dp0"
if not defined DECIPLINE_BUNDLE_NAME set "DECIPLINE_BUNDLE_NAME=Decipline"
echo ============================================
echo   Decipline -- Build Script
echo ============================================

echo [1/3] Checking the source...
python -m unittest discover -s tests -v
if errorlevel 1 goto failed

echo [2/3] Building Decipline.exe...
python -m PyInstaller Decipline.spec --clean --noconfirm
if errorlevel 1 goto failed

echo [3/3] Checking the packaged app...
"dist\%DECIPLINE_BUNDLE_NAME%\Decipline.exe" --smoke-test
if errorlevel 1 goto failed

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\%DECIPLINE_BUNDLE_NAME%\Decipline.exe
echo   Keep the entire Decipline folder together.
echo ============================================
pause
exit /b 0

:failed
echo Build failed. See the error above.
pause
exit /b 1
