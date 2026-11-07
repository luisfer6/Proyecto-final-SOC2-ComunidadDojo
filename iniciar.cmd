@echo off
setlocal
cd /d "%~dp0"
if not defined OLLAMA_MODEL if exist "artifacts\ollama-model.txt" set /p OLLAMA_MODEL=<"artifacts\ollama-model.txt"
if defined OLLAMA_MODEL (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_ollama.ps1"
  if errorlevel 1 goto error
)
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno local...
  python -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import fastapi, openpyxl, reportlab, sklearn, uvicorn, multipart, defusedxml" >nul 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m pip install -r requirements.lock.txt
  if errorlevel 1 goto error
)
echo.
echo SOC Lens disponible en http://127.0.0.1:8000
echo Cierra con Ctrl+C. Los casos se eliminan al detener el servidor.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
if errorlevel 1 goto error
exit /b 0
:error
echo No se pudo iniciar. Revisa el error anterior y el README.
pause
exit /b 1
