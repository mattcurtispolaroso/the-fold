@echo off
REM Build The Fold for Windows — produces dist\The Fold.exe
REM Run from the project root: build\build_windows.bat

setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo ==> Building The Fold (Windows)
echo     Root: %ROOT%

REM Clean previous build artefacts
if exist "dist\The Fold.exe" del /q "dist\The Fold.exe"

REM Run PyInstaller with the shared spec
pyinstaller build\the_fold.spec ^
    --distpath dist ^
    --workpath build\_pyinstaller_work ^
    --noconfirm ^
    --clean

echo.
echo ==> Done. Executable at: dist\The Fold.exe
