#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Virtualenv não encontrado em $ROOT_DIR/.venv"
  echo "Crie o venv e instale as dependências antes de compilar."
  exit 1
fi

cd "$ROOT_DIR"

"$VENV_PYTHON" -m pip install -r requirements.txt -r requirements-build.txt

rm -rf build dist/GirofyPDV dist/GirofyPDV.app

"$VENV_PYTHON" -m PyInstaller \
  --name GirofyPDV \
  --windowed \
  --onedir \
  --clean \
  --add-data "app/templates:app/templates" \
  --add-data "app/static:app/static" \
  --hidden-import pymysql \
  --hidden-import webview \
  --hidden-import webview.platforms.cocoa \
  desktop_launcher.py

if [[ -f ".env" ]]; then
  cp .env dist/.env
  echo "Configuração local copiada para dist/.env"
else
  cp .env.example dist/.env.example
  echo "Nenhum .env encontrado. Modelo copiado para dist/.env.example"
fi

echo
echo "Aplicativo gerado em:"
echo "  $ROOT_DIR/dist/GirofyPDV.app"
echo
echo "Para abrir:"
echo "  open \"$ROOT_DIR/dist/GirofyPDV.app\""
