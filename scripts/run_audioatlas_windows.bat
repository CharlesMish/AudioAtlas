@echo off
setlocal

cd /d "%~dp0\.."

if not exist input_audio mkdir input_audio
if not exist output_reports mkdir output_reports

echo AudioAtlas batch run
echo Input:  input_audio
echo Output: output_reports
echo.

audioatlas batch input_audio --out output_reports
if errorlevel 1 (
  echo.
  echo AudioAtlas failed. Make sure it is installed and available on PATH.
  pause
  exit /b 1
)

if exist output_reports\catalog.html (
  start "" output_reports\catalog.html
) else (
  echo catalog.html was not created.
)

echo.
echo Done. Open output_reports\catalog.html if it did not open automatically.
pause
