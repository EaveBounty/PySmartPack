@echo off
rem One-click run from source (Windows). Sets up a venv on first run, then launches the GUI.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [PySmartPack] 首次运行：创建虚拟环境...
    python -m venv .venv || goto :error
)

call ".venv\Scripts\activate.bat"

".venv\Scripts\python.exe" -c "import PySide6, qfluentwidgets" 2>nul
if errorlevel 1 (
    echo [PySmartPack] 安装依赖中（仅首次）...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

".venv\Scripts\python.exe" -m pip install -e . -q
".venv\Scripts\python.exe" -m pysmartpack
goto :eof

:error
echo [PySmartPack] 启动失败。请确认已安装 Python 3.9+ 并加入 PATH。
pause
