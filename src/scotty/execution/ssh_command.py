from __future__ import annotations

import os
from pathlib import Path

from scotty.parsing.models import ServerDefinition
from scotty.ssh.config import SshConfigFile


class SshCommandBuilder:
    def __init__(self) -> None:
        self._ssh_config: SshConfigFile | None = None
        self._ssh_config_loaded = False

    def build_process_args(
        self, host: str, script: str, env: dict[str, str] | None = None
    ) -> tuple[list[str] | str, dict[str, str], bool]:
        env = dict(env or {})
        env["ENVOY_HOST"] = host
        target = self._resolve_host(host)

        if ServerDefinition.is_local_host(target):
            full_env = {**os.environ, **env}
            return script, full_env, True  # shell=True

        command = self._build_ssh_command(target, script, env)
        return command, os.environ.copy(), True  # shell=True

    def build_command(
        self, host: str, script: str, env: dict[str, str] | None = None
    ) -> str:
        env = dict(env or {})
        env["ENVOY_HOST"] = host
        target = self._resolve_host(host)

        if ServerDefinition.is_local_host(target):
            return script

        return self._build_ssh_command(target, script, env)

    def _resolve_host(self, host: str) -> str:
        self._load_ssh_config()

        if self._ssh_config is None:
            return host

        return self._ssh_config.find_configured_host(host) or host

    def _build_ssh_command(
        self, target: str, script: str, env: dict[str, str]
    ) -> str:
        delimiter = "EOF-SCOTTY"

        exports = []
        for key, value in env.items():
            if value:
                exports.append(f'export {key}="{value}"')

        parts = [
            f"ssh {target} 'bash -se' << \\{delimiter}",
            *exports,
            "set -e",
            script,
            delimiter,
        ]

        return "\n".join(parts)

    def _load_ssh_config(self) -> None:
        if self._ssh_config_loaded:
            return

        self._ssh_config_loaded = True

        config_path = Path.home() / ".ssh" / "config"
        if not config_path.exists():
            return

        self._ssh_config = SshConfigFile.parse(str(config_path))
