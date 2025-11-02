#!/usr/bin/env python3
from pathlib import Path
import sys
from dotenv import dotenv_values

print({"python_version": sys.version.split()[0], "meets_requirement": (sys.version_info.major, sys.version_info.minor) >= (3,10)})

env_path = Path(__file__).resolve().parent / ".env"
print({"env_exists": env_path.exists(), "env_path": str(env_path)})

cfg = dotenv_values(str(env_path)) if env_path.exists() else {}
need = ["BITUNIX_API_KEY","BITUNIX_API_SECRET"]
missing = [k for k in need if not cfg.get(k)]
print({"env_missing": missing})

print({"status": "OK"})
