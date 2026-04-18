from __future__ import annotations

import shlex
import subprocess
from typing import Callable

from scotty.execution.ssh_command import SshCommandBuilder
from scotty.execution.task_result import TaskResult
from scotty.execution.task_runner import TaskRunner
from scotty.parsing.models import HookType, TaskDefinition
from scotty.parsing.parse_result import ParseResult


class Executor:
    def __init__(self, task_runner: TaskRunner | None = None) -> None:
        self.task_runner = task_runner or TaskRunner()

    def run(
        self,
        target: str,
        config: ParseResult,
        env: dict[str, str] | None = None,
        continue_on_error: bool = False,
        pretend: bool = False,
        on_task_start: Callable[[TaskDefinition, int, int], None] | None = None,
        on_task_output: Callable[[str, str, str], None] | None = None,
        on_task_complete: Callable[[TaskDefinition, TaskResult], None] | None = None,
        on_tick: Callable[[], None] | None = None,
    ) -> dict[str, TaskResult]:
        env = env or {}
        tasks = config.resolve_tasks_for_target(target)

        if not tasks:
            return {}

        tasks = self._prepend_variables(tasks, config, env)

        results: dict[str, TaskResult] = {}

        for task in tasks:
            if on_task_start:
                on_task_start(task, len(results), len(tasks))

            if pretend:
                results[task.name] = self._pretend_task(task, config, env)
                if on_task_complete:
                    on_task_complete(task, results[task.name])
                continue

            self._run_hooks(config, HookType.BEFORE)

            result = self.task_runner.run(task, config, env, on_task_output, on_tick)
            results[task.name] = result

            hook_type = HookType.AFTER if result.succeeded() else HookType.ERROR
            self._run_hooks(config, hook_type)

            if on_task_complete:
                on_task_complete(task, result)

            if not result.succeeded() and not continue_on_error:
                break

        total_exit_code = sum(r.exit_code for r in results.values())

        if total_exit_code == 0:
            self._run_hooks(config, HookType.SUCCESS)

        self._run_hooks(config, HookType.FINISHED)

        return results

    def _prepend_variables(
        self,
        tasks: list[TaskDefinition],
        config: ParseResult,
        env: dict[str, str],
    ) -> list[TaskDefinition]:
        preamble = config.variable_preamble

        for key, value in env.items():
            upper_key = key.upper()
            escaped_value = shlex.quote(value)
            preamble += f"\n{upper_key}={escaped_value}"

        debug_trap = "trap 'echo \"SCOTTY_TRACE:$BASH_COMMAND\" >&2' DEBUG"

        preamble = preamble.strip()
        preamble = f"{preamble}\n{debug_trap}" if preamble else debug_trap

        return [
            TaskDefinition(
                name=task.name,
                script=f"{preamble}\n\n{task.script}",
                servers=task.servers,
                parallel=task.parallel,
                confirm=task.confirm,
                emoji=task.emoji,
            )
            for task in tasks
        ]

    def _pretend_task(
        self,
        task: TaskDefinition,
        config: ParseResult,
        env: dict[str, str],
    ) -> TaskResult:
        command_builder = self.task_runner.command_builder
        output = ""

        for server_name in task.servers:
            server = config.get_server(server_name)
            if server is None:
                continue

            for host in server.hosts:
                command = command_builder.build_command(host, task.script, env)
                output += f"# On: {server_name} ({host})\n{command}\n\n"

        return TaskResult(exit_code=0, outputs={"pretend": output}, duration=0.0)

    def _run_hooks(self, config: ParseResult, hook_type: HookType) -> None:
        for hook in config.get_hooks(hook_type):
            subprocess.run(hook.script, shell=True)
