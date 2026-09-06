#!/usr/bin/env python3
"""
RANN Web API Daemon - Auto-restart if crashed, survive session close
"""
import atexit
import os
import signal
import subprocess
import sys
import time

APP_DIR = "/home/userland/rann-agent"
PYTHON = "/home/userland/rann-agent/venv/bin/python3"
API_SCRIPT = f"{APP_DIR}/web_api.py"
PID_FILE = "/tmp/rann_webapi.pid"
RESTART_DELAY = 3

def get_pid():
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except:
        return None

def write_pid():
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup():
    pid = get_pid()
    if pid == os.getpid():
        try: os.unlink(PID_FILE)
        except: pass

def start_api():
    print(f"[{time.strftime('%H:%M:%S')}] Starting RANN Web API...")
    proc = subprocess.Popen(
        [PYTHON, API_SCRIPT],
        cwd=APP_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc.pid

signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
atexit.register(cleanup)
write_pid()

api_pid = start_api()
print(f"[{time.strftime('%H:%M:%S')}] RANN Web API started (PID: {api_pid})")

while True:
    try:
        proc = subprocess.Popen(
            [PYTHON, "-c", 
             "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5555/api/status', timeout=5)",
             "-c", "import sys; sys.exit(0)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.wait()
        time.sleep(30)
    except:
        print(f"[{time.strftime('%H:%M:%S')}] API unreachable, restarting...")
        api_pid = start_api()
        time.sleep(2)
