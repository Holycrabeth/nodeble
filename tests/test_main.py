import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "nodeble", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "scan" in result.stdout
    assert "manage" in result.stdout
    assert "dry-run" in result.stdout
