from __future__ import annotations

import re


class SshConfigFile:
    def __init__(self, groups: list[dict[str, str]] | None = None) -> None:
        self.groups = groups or []

    @staticmethod
    def parse(file_path: str) -> SshConfigFile:
        with open(file_path) as f:
            return SshConfigFile.parse_string(f.read())

    @staticmethod
    def parse_string(string: str) -> SshConfigFile:
        groups: list[dict[str, str]] = []
        index = 0
        is_match_section = False

        for line in string.split("\n"):
            line = line.strip()

            if line == "" or line.startswith("#"):
                continue

            key, value = SshConfigFile._parse_key_value(line)

            if key == "host":
                index += 1
                is_match_section = False
            elif key == "match":
                is_match_section = True

            if not is_match_section:
                while len(groups) <= index:
                    groups.append({})
                groups[index][key] = value

        return SshConfigFile([g for g in groups if g])

    def find_configured_host(self, host: str) -> str | None:
        user, hostname = self._parse_host(host)

        for group in self.groups:
            if not self._group_matches_hostname(group, hostname):
                continue

            if user is not None:
                if group.get("user") != user:
                    continue

            host_value = group.get("host", "")
            return re.sub(r"\s+.*$", "", host_value)

        return None

    @staticmethod
    def _group_matches_hostname(group: dict[str, str], hostname: str) -> bool:
        if group.get("host") == hostname:
            return True
        if group.get("hostname") == hostname:
            return True
        return False

    @staticmethod
    def _parse_host(host: str) -> tuple[str | None, str]:
        if "@" in host:
            parts = host.split("@", 1)
            return parts[0], parts[1]
        return None, host

    @staticmethod
    def _parse_key_value(line: str) -> tuple[str, str]:
        m = re.match(r"^\s*(\S+)\s*=(.*)", line)
        if m:
            return m.group(1).lower(), SshConfigFile._unquote(m.group(2))

        segments = re.split(r"\s+", line, maxsplit=1)
        return segments[0].lower(), SshConfigFile._unquote(segments[1] if len(segments) > 1 else "")

    @staticmethod
    def _unquote(string: str) -> str:
        string = string.strip()
        if string.startswith('"') and string.endswith('"'):
            return string[1:-1]
        return string
