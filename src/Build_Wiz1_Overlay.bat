@echo off
rem Build dist\Wiz1_Korean_Overlay.exe. Uses python on PATH, or the Codex bundled python.
cd /d "%~dp0"
set "PY=python"
python -c "import PIL" >nul 2>nul || set "PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
taskkill /im Wiz1_Korean_Overlay.exe /f >nul 2>nul
"%PY%" -B build.py
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
echo Build complete: dist\Wiz1_Korean_Overlay.exe
pause
