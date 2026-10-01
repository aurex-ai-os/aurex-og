#!/usr/bin/env bash

# Aurex One-Script Launcher

echo "Starting Aurex..."

# Change to the directory where the script is located
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment 'venv' not found. Creating it now..."
    python3 -m venv venv
    echo "Activating venv and installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Activating existing venv..."
    source venv/bin/activate
fi

# Set default ports and run
export APP_PORT="${APP_PORT:-7000}"
export APP_BIND="${APP_BIND:-127.0.0.1}"

echo "Starting Aurex backend on http://$APP_BIND:$APP_PORT"
python3 app.py
