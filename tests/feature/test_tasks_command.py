from __future__ import annotations

import subprocess
import sys


def _run_tasks(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scotty", "tasks", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_lists_tasks_from_bash_file(fixtures_path):
    result = _run_tasks("--conf", str(fixtures_path / "complete.sh"))

    assert result.returncode == 0
    assert "Pull" in result.stdout
    assert "Migrate" in result.stdout
    assert "Clear cache" in result.stdout
    assert "Deploy staging parallel" in result.stdout
    assert "on local" in result.stdout
    assert "on production" in result.stdout


def test_lists_macros_from_bash_file(fixtures_path):
    result = _run_tasks("--conf", str(fixtures_path / "complete.sh"))

    assert result.returncode == 0
    assert "deploy" in result.stdout
    assert "fullDeploy" in result.stdout
    assert "Macros" in result.stdout


def test_errors_when_no_file_found(tmp_path):
    result = _run_tasks(cwd=str(tmp_path))

    assert result.returncode == 1
    assert "No Scotty file found" in result.stdout


def test_works_with_conf_option(fixtures_path):
    result = _run_tasks("--conf", str(fixtures_path / "complete.sh"))
    assert result.returncode == 0
