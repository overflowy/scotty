from __future__ import annotations

import pytest

from scotty.execution.ssh_command import SshCommandBuilder
from scotty.parsing.models import ServerDefinition


@pytest.fixture
def builder() -> SshCommandBuilder:
    return SshCommandBuilder()


def test_server_definition_accepts_string_host():
    server = ServerDefinition("web", "forge@1.1.1.1")
    assert server.name == "web"
    assert server.hosts == ["forge@1.1.1.1"]


def test_server_definition_accepts_list_of_hosts():
    server = ServerDefinition("web", ["forge@1.1.1.1", "forge@2.2.2.2"])
    assert server.name == "web"
    assert server.hosts == ["forge@1.1.1.1", "forge@2.2.2.2"]


def test_single_local_host_is_local():
    assert ServerDefinition("local", "127.0.0.1").is_local() is True


def test_multi_host_server_is_not_local():
    assert ServerDefinition("all", ["127.0.0.1", "forge@1.1.1.1"]).is_local() is False


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "local"])
def test_is_local_host_detects_local_values(host):
    assert ServerDefinition.is_local_host(host) is True


@pytest.mark.parametrize("host", ["forge@1.1.1.1", "example.com", "192.168.1.1"])
def test_is_local_host_rejects_remote_values(host):
    assert ServerDefinition.is_local_host(host) is False


def test_build_command_for_local_returns_script_directly(builder):
    assert builder.build_command("127.0.0.1", 'echo "hello"') == 'echo "hello"'


def test_build_command_for_remote_wraps_in_ssh_heredoc(builder):
    command = builder.build_command("forge@1.1.1.1", 'echo "hello"')
    assert "ssh forge@1.1.1.1" in command
    assert "EOF-SCOTTY" in command
    assert 'echo "hello"' in command


def test_build_command_includes_env_exports(builder):
    command = builder.build_command(
        "forge@1.1.1.1",
        'echo "hello"',
        {"APP_ENV": "production", "BRANCH": "main"},
    )
    assert "export APP_ENV=production" in command
    assert "export BRANCH=main" in command


def test_build_command_quotes_values_with_special_chars(builder):
    command = builder.build_command(
        "forge@1.1.1.1",
        "echo hi",
        {"MSG": 'he said "hi" $HOME'},
    )
    assert "export MSG='he said \"hi\" $HOME'" in command


def test_build_command_includes_set_minus_e(builder):
    command = builder.build_command("forge@1.1.1.1", 'echo "hello"')
    assert "set -e" in command


def test_build_command_exports_scotty_host(builder):
    command = builder.build_command("forge@1.1.1.1", 'echo "hi"')
    assert "export SCOTTY_HOST=forge@1.1.1.1" in command
