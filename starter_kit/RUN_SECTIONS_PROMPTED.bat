@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "AUDIO_DIR=%SCRIPT_DIR%PUT_AUDIO_HERE"
set "REPORTS_DIR=%SCRIPT_DIR%REPORTS"

where audioatlas >nul 2>nul
if errorlevel 1 (
  echo AudioAtlas was not found. Install AudioAtlas first, or run this from an activated environment.
  pause
  exit /b 1
)

if not exist "%AUDIO_DIR%" mkdir "%AUDIO_DIR%"
if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

set /a COUNT=0
for %%E in (wav wave flac ogg aiff aif mp3) do (
  for /f "delims=" %%F in ('dir /b /a-d "%AUDIO_DIR%\*.%%E" 2^>nul') do (
    set /a COUNT+=1
    set "FILE_!COUNT!=%AUDIO_DIR%\%%F"
    set "NAME_!COUNT!=%%F"
  )
)

if !COUNT! EQU 0 (
  echo Put one audio file into PUT_AUDIO_HERE, then run this again.
  pause
  exit /b 1
)

if !COUNT! EQU 1 (
  set "CHOICE=1"
) else (
  echo More than one audio file was found. Choose one:
  for /L %%I in (1,1,!COUNT!) do call echo   %%I^) %%NAME_%%I%%
  set /p "CHOICE=Enter a number: "
)

call set "INPUT=%%FILE_%CHOICE%%%"
if not defined INPUT (
  echo Invalid selection.
  pause
  exit /b 1
)

for %%F in ("%INPUT%") do set "STEM=%%~nF"
set "OUT_DIR=%REPORTS_DIR%\%STEM%_sections"

set /p "SECTION_COUNT=Number of sections: "
if "%SECTION_COUNT%"=="" (
  echo Enter a section count of 1 or more.
  pause
  exit /b 1
)

set "SECTION_ARGS="
for /L %%I in (1,1,%SECTION_COUNT%) do (
  echo.
  set /p "SEC_NAME=Section %%I name: "
  set /p "SEC_START=Section %%I start time in seconds: "
  set /p "SEC_END=Section %%I end time in seconds (blank for EOF on final section): "
  set "SEC_NAME=!SEC_NAME::=_!"
  set "SEC_NAME=!SEC_NAME: =_!"
  set "SECTION_ARGS=!SECTION_ARGS! --section !SEC_NAME!:!SEC_START!:!SEC_END!"
)

echo.
echo Chosen file: %INPUT%
echo Output folder: %OUT_DIR%
echo.

call audioatlas sections "%INPUT%" --out "%OUT_DIR%" !SECTION_ARGS!
set "STATUS=%ERRORLEVEL%"

echo.
if "%STATUS%"=="0" (
  echo Section report succeeded.
  echo Output folder: %OUT_DIR%
  echo Open report.html inside a section folder, or open section_index.md.
  start "" "%OUT_DIR%"
) else (
  echo Section report failed.
  echo Output folder: %OUT_DIR%
)

pause
exit /b %STATUS%
