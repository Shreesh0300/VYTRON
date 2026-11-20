"""
VYTRON AIOps — Multi-Process Launcher
Starts all four services as separate processes on one machine.

Usage:
    python start.py          # Start all services
    python start.py --stop   # Stop all services
"""

import subprocess
import sys
import os
import signal
import time
import argparse
import socket

ROOT = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name": "Central Backend",
        "module": "backend.main:app",
        "port": 8000,
        "color": "\033[94m",  # Blue
    },
    {
        "name": "Simulator",
        "module": "simulator.main:app",
        "port": 8001,
        "color": "\033[92m",  # Green
    },
    {
        "name": "Local Collector",
        "module": "collector.main:app",
        "port": 8002,
        "color": "\033[93m",  # Yellow
    },
]

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"


def get_python_executable() -> str:
    """Prefer virtualenv python if available, otherwise fallback to sys.executable."""
    venv_python = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    # Unix virtual environment fallback
    venv_python_unix = os.path.join(ROOT, ".venv", "bin", "python")
    if os.path.exists(venv_python_unix):
        return venv_python_unix
    return sys.executable


def is_port_in_use(port: int) -> bool:
    """Check if a local port has an active listener."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port_free(port: int, max_wait: float = 3.0) -> bool:
    """Wait until port is completely released."""
    start = time.time()
    while time.time() - start < max_wait:
        if not is_port_in_use(port):
            return True
        time.sleep(0.2)
    return False


def stop_services():
    """Kill any running processes on our ports."""
    ports = [8000, 8001, 8002, 5500]
    pids_killed = set()

    for port in ports:
        try:
            if sys.platform == "win32":
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True
                )
                for line in result.stdout.splitlines():
                    # Look for listening sockets on this port
                    if f":{port}" in line and ("LISTENING" in line or "TIME_WAIT" not in line):
                        parts = line.strip().split()
                        if parts:
                            pid = parts[-1]
                            if pid.isdigit() and pid != "0" and pid not in pids_killed:
                                pids_killed.add(pid)
                                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                                print(f"  Killed previous process on port {port} (PID {pid})")
        except Exception as e:
            print(f"  Could not inspect port {port}: {e}")

    if pids_killed:
        time.sleep(1.0)

    for port in ports:
        wait_for_port_free(port, max_wait=2.0)


def start_services():
    """Launch all services as subprocesses."""
    # Ensure any lingering processes on ports 8000, 8001, 8002, 5500 are stopped first
    stop_services()

    python_bin = get_python_executable()

    processes = []
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT

    print(f"\n{BOLD}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║    VYTRON — Autonomous Observability Platform    ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════╝{RESET}\n")
    print(f"  Python runtime: {python_bin}\n")

    logs_dir = os.path.join(ROOT, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    # Start backend, then simulator, then collector
    for svc in SERVICES:
        # Verify port is free
        if is_port_in_use(svc["port"]):
            print(f"{YELLOW}⚠ Port {svc['port']} still busy; waiting for socket release...{RESET}")
            wait_for_port_free(svc["port"], max_wait=4.0)

        cmd = [
            python_bin, "-m", "uvicorn",
            svc["module"],
            "--host", "0.0.0.0",
            "--port", str(svc["port"]),
            "--log-level", "info",
        ]
        log_file_path = os.path.join(logs_dir, f"{svc['name'].lower().replace(' ', '_')}.log")
        log_file = open(log_file_path, "w", encoding="utf-8")  # Fresh truncate on start
        print(f"{svc['color']}▶ Starting {svc['name']} on port {svc['port']} (logs: logs/{os.path.basename(log_file_path)})...{RESET}")
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        processes.append((svc, proc, log_file_path))
        time.sleep(1.2)  # Stagger starts

    # Start frontend static server
    frontend_dir = os.path.join(ROOT, "frontend")
    frontend_cmd = [
        python_bin, "-m", "http.server", "5500",
        "--directory", frontend_dir,
        "--bind", "0.0.0.0",
    ]
    fe_log_path = os.path.join(logs_dir, "frontend.log")
    fe_log = open(fe_log_path, "w", encoding="utf-8")
    print(f"\033[95m▶ Starting Frontend on port 5500 (logs: logs/frontend.log)...{RESET}")
    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        env=env,
        stdout=fe_log,
        stderr=subprocess.STDOUT,
    )
    processes.append(({"name": "Frontend", "port": 5500, "color": "\033[95m"}, frontend_proc, fe_log_path))

    print(f"\n{BOLD}{GREEN}All services successfully initialized!{RESET}\n")
    print(f"  🌐 Dashboard:    http://localhost:5500")
    print(f"  🖥️  Backend API:  http://localhost:8000/docs")
    print(f"  📡 Simulator:    http://localhost:8001/docs")
    print(f"  🔒 Collector:    http://localhost:8002/docs")
    print(f"\n  Press Ctrl+C to stop all services.\n")

    failed_services = set()

    # Monitoring loop
    try:
        while True:
            for svc, proc, log_path in processes:
                svc_name = svc["name"]
                if proc.poll() is not None and svc_name not in failed_services:
                    failed_services.add(svc_name)
                    print(f"{RED}✖ {svc_name} exited with code {proc.returncode}{RESET}")
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = [line.strip() for line in f.readlines() if line.strip()]
                                if lines:
                                    print(f"  {YELLOW}Recent lines from {os.path.basename(log_path)}:{RESET}")
                                    for line in lines[-5:]:
                                        print(f"    {line}")
                        except Exception:
                            pass

            # If all services died, break out
            if len(failed_services) == len(processes):
                print(f"\n{RED}All services have stopped.{RESET}")
                break

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopping all services...{RESET}")
    finally:
        for svc, proc, _ in processes:
            if proc.poll() is None:
                print(f"  ■ Stopping {svc['name']}...")
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
        print(f"{BOLD}All services stopped cleanly.{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VYTRON AIOps Launcher")
    parser.add_argument("--stop", action="store_true", help="Stop all services")
    args = parser.parse_args()

    if args.stop:
        stop_services()
    else:
        start_services()
