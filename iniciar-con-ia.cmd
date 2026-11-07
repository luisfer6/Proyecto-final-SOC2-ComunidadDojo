@echo off
setlocal
cd /d "%~dp0"
set "OLLAMA_MODEL=qwen3:4b"
call iniciar.cmd
