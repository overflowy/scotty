from __future__ import annotations

import subprocess
import sys


def _run_scotty(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scotty", "run", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_runs_task_in_pretend_mode(fixtures_path):
    result = _run_scotty("pull", "--pretend", "--conf", str(fixtures_path / "complete.sh"))

    assert result.returncode == 0
    assert "pull" in result.stdout.lower()


def test_errors_for_unknown_task(fixtures_path):
    result = _run_scotty("nonexistent", "--conf", str(fixtures_path / "complete.sh"))

    assert result.returncode == 1
    assert "not defined" in result.stdout


def test_runs_with_conf_option(fixtures_path):
    result = _run_scotty("migrate", "--pretend", "--conf", str(fixtures_path / "complete.sh"))

    assert result.returncode == 0
    assert "migrate" in result.stdout.lower()


def test_runs_local_tasks_cleanly(fixtures_path):
    result = _run_scotty("deploy", "--conf", str(fixtures_path / "local-only.sh"))

    assert result.returncode == 0
    assert "hello from scotty" in result.stdout
    assert "finished" in result.stdout
    assert "Running deploy" in result.stdout
    assert "Greet" in result.stdout
    assert "Done" in result.stdout
    assert "Invalid option specified" not in result.stdout


def test_errors_when_no_file_found(tmp_path):
    result = _run_scotty("deploy", cwd=str(tmp_path))

    assert result.returncode == 1
    assert "No Scotty file found" in result.stdout


def test_errors_friendly_on_macro_with_missing_task(tmp_path):
    scotty_file = tmp_path / "Scotty.sh"
    scotty_file.write_text(
        "# @servers local=127.0.0.1\n"
        "# @macro deploy pull ghost\n"
        "\n"
        "# @task on:local\n"
        "pull() { echo hi; }\n"
    )

    result = _run_scotty("deploy", "--conf", str(scotty_file))

    assert result.returncode == 1
    assert "ghost" in result.stdout
    assert "undefined" in result.stdout
