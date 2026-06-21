#!/usr/bin/env bash
# One-click run from source (macOS / Linux). Creates a venv on first run, then launches the GUI.
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[PySmartPack] 首次运行：创建虚拟环境..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import PySide6, qfluentwidgets" 2>/dev/null; then
    echo "[PySmartPack] 安装依赖中（仅首次）..."
    python -m pip install -r requirements.txt
fi

python -m pip install -e . -q
exec python -m pysmartpack
