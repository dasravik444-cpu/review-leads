@echo off
rem Double-click to run on Windows (docs/LOCAL.md). The first time it installs what it needs.
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if not exist settings.txt (
  copy /y settings-example.txt settings.txt >nul
  echo Your settings file "settings.txt" opens now in Notepad.
  echo Fill it in, save with Ctrl+S, close Notepad - then double-click run_leads again.
  start /wait notepad settings.txt
  pause
  exit /b
)
if not exist data\.installed (
  echo Installing the first time - this takes a few minutes...
  %PY% -m pip install --upgrade pip
  %PY% -m pip install -r requirements.txt "duckdb>=1.1" || goto :failed
  if not exist data mkdir data
  echo ok> data\.installed
)
%PY% scripts\local_run.py leads %*
echo.
pause
exit /b
:failed
echo.
echo Installing failed. Is Python installed? See docs\LOCAL.md, step 1.
pause
