@echo off
setlocal
cd /d "%~dp0"
set "UV_PROJECT_ENVIRONMENT=%~dp0.runtime\windows\venv"
set "UV_PYTHON_INSTALL_DIR=%~dp0.runtime\windows\python"
set "SDL_VIDEODRIVER="
set "SDL_AUDIODRIVER="
set "DND_UV=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%DND_UV%" set "DND_UV=uv"
"%DND_UV%" run --locked --python 3.13.12 python -m game --fullscreen %*
if errorlevel 1 pause
