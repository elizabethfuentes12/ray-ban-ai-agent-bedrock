#!/bin/bash
set -e
cd agent_files

uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.11 \
  --target=deployment_package \
  --only-binary=:all: \
  -r requirements.txt

cd deployment_package && zip -r ../deployment_package.zip .
cd .. && zip deployment_package.zip *.py requirements.txt
echo "Created: agent_files/deployment_package.zip"
