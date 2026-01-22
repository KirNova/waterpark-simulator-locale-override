@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%SCRIPT_DIR%patch_staff_only.py" %*
  goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
  python "%SCRIPT_DIR%patch_staff_only.py" %*
  goto :eof
)

where python3 >nul 2>nul
if %errorlevel%==0 (
  python3 "%SCRIPT_DIR%patch_staff_only.py" %*
  goto :eof
)

echo Python 3.8+ not found. Install Python and try again.
exit /b 1
