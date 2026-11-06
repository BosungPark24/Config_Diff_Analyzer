@echo off
setlocal
cd /d "%~dp0"
set "APP_VERSION=v0.2"
set "EXE_NAME=ConfigAnalyzer_%APP_VERSION%"
set "BUILD_WORK=build_%RANDOM%_%RANDOM%"
if not exist "%BUILD_WORK%" mkdir "%BUILD_WORK%"

echo Building %EXE_NAME%.exe from:
echo   %~dp0was_config_analyzer.py
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m PyInstaller --noconfirm --onefile --noconsole --name "%EXE_NAME%" --specpath "%BUILD_WORK%" --workpath "%BUILD_WORK%" --distpath dist was_config_analyzer.py
    if not errorlevel 1 goto build_succeeded
)

echo Python launcher command failed or was not found. Trying python...
where python >nul 2>nul
if not errorlevel 1 (
    python -m PyInstaller --noconfirm --onefile --noconsole --name "%EXE_NAME%" --specpath "%BUILD_WORK%" --workpath "%BUILD_WORK%" --distpath dist was_config_analyzer.py
    if not errorlevel 1 goto build_succeeded
)

echo Searching the current user's local Python installation...
set "PYTHON_EXE="
for /d %%P in ("%USERPROFILE%\AppData\Local\Programs\Python\Python*") do (
    if exist "%%~fP\python.exe" set "PYTHON_EXE=%%~fP\python.exe"
)
if not defined PYTHON_EXE goto build_failed
"%PYTHON_EXE%" -m PyInstaller --noconfirm --onefile --noconsole --name "%EXE_NAME%" --specpath "%BUILD_WORK%" --workpath "%BUILD_WORK%" --distpath dist was_config_analyzer.py
if errorlevel 1 goto build_failed

:build_succeeded
if not exist "%~dp0dist\%EXE_NAME%.exe" goto build_failed
echo.
echo Build complete: %~dp0dist\%EXE_NAME%.exe
echo Run this EXE to use the updated version.
pause
exit /b 0

:build_failed
echo.
echo Build failed. Close %EXE_NAME% if it is running, then retry.
echo Check the Python and PyInstaller error above for any other cause.
pause
exit /b 1
