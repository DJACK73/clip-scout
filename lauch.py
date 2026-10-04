cd ~/clip-scout
cat > scripts/launch.py << 'EOF'
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8501"


def running() -> bool:
    return subprocess.run(["pgrep", "-f", "streamlit run app/[d]ashboard.py"], capture_output=True).returncode == 0


def open_browser() -> None:
    subprocess.run(["cmd.exe", "/c", "start", URL], cwd="/mnt/c", capture_output=True)


def main() -> int:
    if running():
        open_browser()
        return 0
    (ROOT / "logs").mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    cmd = [sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless", "true", "--server.address", "127.0.0.1"]
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env)
    time.sleep(6)
    open_browser()
    return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
EOF
scripts/stop.sh
python scripts/launch.py