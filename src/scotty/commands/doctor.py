from __future__ import annotations

import shlex
import subprocess
import re
import time

from scotty.parsing.parse_result import ParseResult
from scotty.ui import output as out


SSH_TIMEOUT = 5
REMOTE_TOOLS_TIMEOUT = 10


def handle_doctor(args, file_path: str | None, parser_factory) -> int:
    has_failures = False

    out.writeln()
    out.writeln("  \033[1mScotty Doctor\033[0m")
    out.writeln("  \033[38;2;74;85;104mChecking your configuration, servers, and remote tools.\033[0m")
    out.writeln()

    if file_path is None:
        _write_failure("No Scotty file found")
        return 1

    _write_success(f"Scotty file found ({file_path})")

    try:
        parser = parser_factory(file_path)
        config = parser.parse(file_path)
    except Exception as e:
        _write_failure(f"File parsing failed: {e}")
        return 1

    task_count = len(config.tasks)
    macro_count = len(config.macros)
    _write_success(f"File parsed successfully ({task_count} tasks, {macro_count} macros)")

    # Check servers defined
    if not config.servers:
        _write_failure("No servers defined")
        has_failures = True
    else:
        _write_success(f"{len(config.servers)} server(s) defined")

    # Check tasks defined
    if not config.tasks:
        _write_failure("No tasks defined")
        has_failures = True
    else:
        _write_success(f"{len(config.tasks)} task(s) defined")

    # Check macro tasks exist
    if config.macros:
        invalid = _find_invalid_macro_references(config)
        if invalid:
            for ref in invalid:
                _write_failure(ref)
            has_failures = True
        else:
            _write_success("All macro tasks exist")

    out.writeln()

    # Check servers
    reachable_remote_hosts: list[dict[str, str]] = []

    if config.servers:
        out.writeln("  \033[1mServers\033[0m")
        out.writeln("  \033[38;2;74;85;104mTesting SSH connectivity to each remote server.\033[0m")

        for server in config.servers.values():
            if server.is_local():
                _write_success(f"{server.name} — skipped (local)")
                continue

            for host in server.hosts:
                reachable = _check_ssh_connectivity(server.name, host)
                if reachable:
                    reachable_remote_hosts.append({"name": server.name, "host": host})
                else:
                    has_failures = True

    for entry in reachable_remote_hosts:
        out.writeln()
        _check_remote_tools(entry["name"], entry["host"])

    out.writeln()

    if has_failures:
        out.writeln(
            "  \033[31;1mSome checks failed.\033[0m "
            "Fix the issues above and run \033[1mscotty doctor\033[0m again."
        )
        out.writeln()
        return 1

    out.writeln("  \033[32;1mEverything looks good.\033[0m You're ready to deploy.")
    out.writeln()
    return 0


def _find_invalid_macro_references(config: ParseResult) -> list[str]:
    invalid = []
    for macro in config.macros.values():
        for task_name in macro.tasks:
            if config.get_task(task_name) is None:
                invalid.append(
                    f'Macro "{macro.name}" references undefined task "{task_name}"'
                )
    return invalid


def _check_ssh_connectivity(name: str, host: str) -> bool:
    start = time.monotonic()
    command = f"ssh -o ConnectTimeout=5 -o BatchMode=yes {shlex.quote(host)} 'echo ok'"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, timeout=SSH_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        _write_failure(f"{name} ({host}) — connection timed out")
        return False

    if result.returncode != 0:
        _write_failure(f"{name} ({host}) — connection failed")
        return False

    duration = round(time.monotonic() - start, 1)
    _write_success(f"{name} ({host}) — connected in {duration}s")
    return True


def _check_remote_tools(name: str, host: str) -> None:
    out.writeln(f"  \033[1mRemote tools on {name}\033[0m")
    out.writeln(f"  \033[38;2;74;85;104mChecking which tools are available on {host}.\033[0m")

    tool_check_script = "; ".join([
        "php -v 2>/dev/null | head -1",
        "composer --version 2>/dev/null",
        "node -v 2>/dev/null",
        "npm -v 2>/dev/null",
        "git --version 2>/dev/null",
    ])

    command = f"ssh -o ConnectTimeout=5 -o BatchMode=yes {shlex.quote(host)} '{tool_check_script}'"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, timeout=REMOTE_TOOLS_TIMEOUT, text=True
        )
    except subprocess.TimeoutExpired:
        _write_failure("Could not check remote tools: timeout")
        return

    output = result.stdout.strip()
    lines = output.split("\n") if output else []

    _report_tool("php", _extract_version(lines, r"^PHP (\d+\.\d+\.\d+)"))
    _report_tool("composer", _extract_version(lines, r"Composer.*?(\d+\.\d+\.\d+)"))
    _report_tool("node", _extract_version(lines, r"^v(\d+\.\d+\.\d+)"))
    _report_tool("npm", _extract_version(lines, r"^(\d+\.\d+\.\d+)$"))
    _report_tool("git", _extract_version(lines, r"git version (\d+\.\d+\.\d+)"))


def _extract_version(lines: list[str], pattern: str) -> str | None:
    for line in lines:
        m = re.match(pattern, line.strip())
        if m:
            return m.group(1)
    return None


def _report_tool(tool: str, version: str | None) -> None:
    if version is None:
        out.writeln(f"  \033[38;2;74;85;104m-\033[0m {tool} not found")
        return
    _write_success(f"{tool} {version}")


def _write_success(message: str) -> None:
    out.writeln(f"  \033[32m✓\033[0m {message}")


def _write_failure(message: str) -> None:
    out.writeln(f"  \033[31m✗\033[0m {message}")
