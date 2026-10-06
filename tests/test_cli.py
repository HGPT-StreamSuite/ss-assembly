import json
import subprocess
import sys

def test_installed_cli():
    result = subprocess.run([sys.executable, "-m", "ss_assembly", "demo"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True

def test_console_entrypoint():
    import shutil
    executable = shutil.which("ss-assembly")
    assert executable is not None
    result = subprocess.run([executable, "demo"], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
