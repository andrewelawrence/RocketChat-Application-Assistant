#!/bin/bash
# test.sh

if [ $# -gt 1 ]; then
  echo "Usage: $0"
fi

source config/.env
python config/load_envs.py app.py
