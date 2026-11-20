"""
VYTRON — Single-Process Application Launcher
Runs the complete 5-Server Infrastructure Monitoring & Incident Prioritization Platform
on http://localhost:8000.
"""

import os
import sys
import time
import socket
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))

def get_python_executable() -> str:
    venv_python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    venv_python_unix = os.path.join(ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_python_unix):
        return venv_python_unix
    return sys.executable

def free_port_8000():
    """Ensure port 8000 is free before starting."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if ":8000" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and pid != "0":
                            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                            print(f"[Launcher] Freed port 8000 (killed PID {pid})")
        except Exception:
            pass

def main():
    free_port_8000()
    time.sleep(0.5)

    py_exe = get_python_executable()
    print("=" * 70)
    print("  VYTRON — 5-SERVER INFRASTRUCTURE MONITORING & INCIDENT PRIORITIZATION")
    print("=" * 70)
    print(f"  Python:    {py_exe}")
    print("  Dashboard: http://localhost:8000")
    print("  API Docs:  http://localhost:8000/docs")
    print("  WebSocket: ws://localhost:8000/ws")
    print("  Architecture: In-memory simulation (No DB reliance)")
    print("=" * 70)
    print("  Starting unified server on port 8000...")
    print("  Press Ctrl+C to stop.\n")

    cmd = [
        py_exe,
        "-m", "uvicorn",
        "server.app:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    ]

    try:
        subprocess.run(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down VYTRON server cleanly.")

if __name__ == "__main__":
    main()
