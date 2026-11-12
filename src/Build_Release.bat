@echo off
rem Build the release package in dist\release (exe, README, font license).
cd /d "%~dp0"
set "PY=python"
python -c "import PIL" >nul 2>nul || set "PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
"%PY%" -B build.py --release
if errorlevel 1 (echo Build failed. & pause & exit /b 1)
echo Release build complete: dist\release
pause
