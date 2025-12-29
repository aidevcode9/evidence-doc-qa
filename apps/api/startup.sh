#!/usr/bin/env bash
set -euo pipefail

echo "Startup debug: listing /home/site/wwwroot"
pwd
ls -la

if [ -d "/home/site/wwwroot/.python_packages/lib/site-packages" ]; then
  echo "Startup debug: listing site-packages (first 50)"
  ls -la /home/site/wwwroot/.python_packages/lib/site-packages | head -n 50
else
  echo "Startup debug: site-packages directory not found"
fi

export PYTHONPATH="/home/site/wwwroot/.python_packages/lib/site-packages:${PYTHONPATH:-}"

python3 - <<'PY'
import os
import sys

print("PYTHONPATH:", os.getenv("PYTHONPATH"))
print("sys.path:", sys.path)
try:
    import uvicorn
    print("uvicorn version:", uvicorn.__version__)
except Exception as exc:
    print("uvicorn import failed:", exc)
PY

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
