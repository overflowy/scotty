from __future__ import annotations

import fcntl
import os
import subprocess
import time
from typing import Callable

from scotty.execution.ssh_command import SshCommandBuilder
from scotty.execution.task_result import TaskResult
from scotty.parsing.models import TaskDefinition
from scotty.parsing.parse_result import ParseResult


class TaskRunner:
    OUT = "out"
    ERR = "err"

    def __init__(self, command_builder: SshCommandBuilder | None = None) -> None:
        self.command_builder = command_builder or SshCommandBuilder()

    def run(
        self,
        task: TaskDefinition,
        config: ParseResult,
        env: dict[str, str] | None = None,
        on_output: Callable[[str, str, str], None] | None = None,
        on_tick: Callable[[], None] | None = None,
    ) -> TaskResult:
        start_time = time.monotonic()

        server_map = self._resolve_server_map(task, config)

        if not server_map:
            return TaskResult(exit_code=0, duration=time.monotonic() - start_time)

        processes = self._build_processes(server_map, task.script, env or {})

        if task.parallel:
            result = self._run_parallel(processes, on_output, on_tick)
        else:
            result = self._run_sequential(processes, on_output, on_tick)

        result.duration = time.monotonic() - start_time
        return result

    def _resolve_server_map(
        self, task: TaskDefinition, config: ParseResult
    ) -> dict[str, str]:
        server_map: dict[str, str] = {}

        for server_name in task.servers:
            server = config.get_server(server_name)
            if server is None:
                continue

            if len(server.hosts) == 1:
                server_map[server_name] = server.hosts[0]
            else:
                for host in server.hosts:
                    server_map[host] = host

        return server_map

    def _build_processes(
        self, server_map: dict[str, str], script: str, env: dict[str, str]
    ) -> dict[str, subprocess.Popen]:
        processes: dict[str, subprocess.Popen] = {}

        for name, host in server_map.items():
            command, full_env, shell = self.command_builder.build_process_args(
                host, script, env
            )
            processes[name] = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=full_env,
            )

        for process in processes.values():
            for stream in (process.stdout, process.stderr):
                if stream:
                    fd = stream.fileno()
                    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        return processes

    def _run_sequential(
        self,
        processes: dict[str, subprocess.Popen],
        on_output: Callable[[str, str, str], None] | None,
        on_tick: Callable[[], None] | None,
    ) -> TaskResult:
        outputs: dict[str, str] = {}
        exit_code = 0
        failed_host: str | None = None

        for name, process in processes.items():
            outputs[name] = ""

            while process.poll() is None:
                self._gather_output({name: process}, outputs, on_output)
                if on_tick:
                    on_tick()
                time.sleep(0.08)

            self._gather_output({name: process}, outputs, on_output)

            host_exit_code = process.returncode or 0
            exit_code += host_exit_code

            if host_exit_code != 0 and failed_host is None:
                failed_host = name

        return TaskResult(
            exit_code=exit_code, outputs=outputs, failed_host=failed_host
        )

    def _run_parallel(
        self,
        processes: dict[str, subprocess.Popen],
        on_output: Callable[[str, str, str], None] | None,
        on_tick: Callable[[], None] | None,
    ) -> TaskResult:
        outputs: dict[str, str] = {name: "" for name in processes}
        failed_host: str | None = None

        while any(p.poll() is None for p in processes.values()):
            self._gather_output(processes, outputs, on_output)
            if on_tick:
                on_tick()
            time.sleep(0.08)

        self._gather_output(processes, outputs, on_output)

        exit_code = 0
        for name, process in processes.items():
            host_exit_code = process.returncode or 0
            exit_code += host_exit_code
            if host_exit_code != 0 and failed_host is None:
                failed_host = name

        return TaskResult(
            exit_code=exit_code, outputs=outputs, failed_host=failed_host
        )

    def _gather_output(
        self,
        processes: dict[str, subprocess.Popen],
        outputs: dict[str, str],
        on_output: Callable[[str, str, str], None] | None,
    ) -> None:
        for name, process in processes.items():
            if process.stdout:
                stdout = self._read_available(process.stdout)
                if stdout:
                    outputs[name] += stdout
                    if on_output:
                        on_output(self.OUT, name, stdout)

            if process.stderr:
                stderr = self._read_available(process.stderr)
                if stderr:
                    outputs[name] += stderr
                    if on_output:
                        on_output(self.ERR, name, stderr)

    @staticmethod
    def _read_available(stream) -> str:
        try:
            data = stream.read()
            if data:
                return data.decode("utf-8", errors="replace")
        except (BlockingIOError, TypeError):
            pass
        return ""
