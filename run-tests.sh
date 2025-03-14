#!/bin/bash

# Install test dependencies
pip install -r test-requirements.txt

# Run unit tests
echo "Running unit tests..."
python -m pytest tests/unit -v

# Run integration tests
echo "Running integration tests..."
python -m pytest tests/integration -v

# Run all tests with coverage
echo "Running all tests with coverage..."
python -m pytest --cov=gitmirror --cov-report=term-missing 