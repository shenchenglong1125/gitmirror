#!/bin/bash
set -e

# Create necessary directories
mkdir -p /app/logs
mkdir -p /app/data/config

# Set default permissions
chmod -R 755 /app/logs
chmod -R 755 /app/data/config

# Generate a random SECRET_KEY if not provided
if [ -z "$SECRET_KEY" ]; then
    echo "No SECRET_KEY found in environment, generating a random one..."
    export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "Generated SECRET_KEY: $SECRET_KEY"
fi

# Check if .env file exists, if not, create it from example
if [ ! -f .env ]; then
    echo "No .env file found, creating from .env.example..."
    cp .env.example .env
    echo "Please update the .env file with your credentials."
fi

# Check the first argument to determine what to run
if [ "$1" = "web" ]; then
    echo "Starting web UI..."
    exec python -m gitmirror.web
elif [ "$1" = "mirror" ]; then
    echo "Running mirror script..."
    exec python -m gitmirror.mirror
else
    echo "Unknown command: $1"
    echo "Usage: $0 [web|mirror]"
    exit 1
fi 