from __future__ import annotations

import textwrap

from scotty.ssh.config import SshConfigFile


def test_parses_simple_host_entry():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host myserver
                HostName 192.168.1.100
                User deploy
            """
        )
    )
    assert config.find_configured_host("myserver") == "myserver"


def test_parses_host_with_hostname_for_lookup():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host production
                HostName 10.0.0.5
                User forge
            """
        )
    )
    assert config.find_configured_host("10.0.0.5") == "production"


def test_parses_key_equals_value_format():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host myserver
                HostName=192.168.1.100
                User=deploy
            """
        )
    )
    assert config.find_configured_host("myserver") == "myserver"


def test_skips_comments_and_blank_lines():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            # This is a comment

            Host myserver
                # Another comment
                HostName 192.168.1.100

                User deploy
            """
        )
    )
    assert config.find_configured_host("myserver") == "myserver"


def test_find_configured_host_matches_by_name():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host server-a
                HostName 10.0.0.1
                User deploy

            Host server-b
                HostName 10.0.0.2
                User forge
            """
        )
    )
    assert config.find_configured_host("server-a") == "server-a"
    assert config.find_configured_host("server-b") == "server-b"


def test_returns_none_for_unknown_host():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host myserver
                HostName 192.168.1.100
            """
        )
    )
    assert config.find_configured_host("unknown") is None


def test_handles_user_at_host_format():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host production
                HostName 10.0.0.5
                User forge
            """
        )
    )
    assert config.find_configured_host("forge@production") == "production"


def test_skips_match_sections():
    config = SshConfigFile.parse_string(
        textwrap.dedent(
            """\
            Host myserver
                HostName 192.168.1.100
                User deploy

            Match host *.example.com
                User admin
                ForwardAgent yes

            Host another
                HostName 10.0.0.1
            """
        )
    )
    assert config.find_configured_host("myserver") == "myserver"
    assert config.find_configured_host("another") == "another"
