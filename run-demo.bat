@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
set DEMO=1
set DATABASE=%CD%\instance\demo.sqlite
if not exist "%DATABASE%" (
  .venv\Scripts\python.exe -m flask --app app seed-demo
  if errorlevel 1 goto failed
)
echo.
echo Open http://localhost:5000 in your browser after Flask starts.
echo Dashboard: admin / MicrogridDemo!2026
echo Enumerator: maria / FieldworkDemo!2026
echo Keep this window open while using the app. Press Ctrl+C to stop.
echo.
.venv\Scripts\python.exe app.py
pause
exit /b
:failed
echo Setup failed. Check the error above and your internet connection.
pause
exit /b 1
