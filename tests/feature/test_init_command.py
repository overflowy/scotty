from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from scotty.commands import init_cmd


@pytest.fixture
def chdir_to_tmp(tmp_path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_creates_scotty_sh_with_host(chdir_to_tmp, monkeypatch):
    monkeypatch.setattr(init_cmd, "text", lambda **kwargs: "forge@example.com")

    exit_code = init_cmd.handle_init(Namespace())

    assert exit_code == 0

    path = chdir_to_tmp / "Scotty.sh"
    assert path.exists()

    content = path.read_text()
    assert "forge@example.com" in content
    assert "@servers" in content
    assert "@task" in content


def test_fails_when_file_already_exists(chdir_to_tmp, monkeypatch):
    (chdir_to_tmp / "Scotty.sh").write_text("existing")
    monkeypatch.setattr(init_cmd, "text", lambda **kwargs: "forge@example.com")

    assert init_cmd.handle_init(Namespace()) == 1
