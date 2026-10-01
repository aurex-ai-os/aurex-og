#!/bin/bash
# Build a standalone Linux executable for Aurex using PyInstaller

echo "Installing build dependencies..."
./.venv/bin/python -m pip install --upgrade pip pyinstaller

echo "Building standalone executable..."
rm -rf build dist

./.venv/bin/python -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --noconsole \
    --icon=static/icon.png \
    --name Aurex \
    --hidden-import webview \
    --add-data "static:static" \
    --hidden-import webview \
    --add-data "scripts:scripts" \
    --hidden-import webview \
    --add-data "mcp_servers:mcp_servers" \
    --hidden-import webview \
    --add-data "config:config" \
    --hidden-import webview \
    --add-data ".env.example:.env.example" \
    launcher.py

echo "Build complete! Your Linux app is in dist/Aurex"
