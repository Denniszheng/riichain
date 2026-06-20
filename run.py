#!/usr/bin/env python3
"""RiiChain 启动脚本"""
import os, sys, time
from subprocess import Popen, DEVNULL
import urllib.request

os.chdir("C:/Users/96153/projects/riichain")

proc = Popen(
    [
        "C:/Users/96153/.workbuddy/binaries/python/versions/3.13.12/Scripts/uvicorn.exe",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8081",
        "--workers", "1",
    ],
    stdout=DEVNULL, stderr=DEVNULL,
    cwd="C:/Users/96153/projects/riichain",
)

print(f"PID={proc.pid}", flush=True)

# 等待服务就绪（最多 10 秒）
for i in range(10):
    time.sleep(1)
    try:
        urllib.request.urlopen("http://localhost:8081/health", timeout=1)
        print("READY", flush=True)
        break
    except Exception:
        pass
else:
    print("TIMEOUT", flush=True)
    proc.kill()
    sys.exit(1)

# 保持运行
proc.wait()
