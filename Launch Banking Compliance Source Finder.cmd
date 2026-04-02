@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python environment not found. Please contact the support team.','Banking Compliance Source Finder')" >nul 2>&1
  exit /b 1
)

start "" "http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501
