from __future__ import annotations

import atexit
import os
import re
import signal
import sys
import time

from scotty.execution.executor import Executor
from scotty.execution.task_result import TaskResult
from scotty.parsing.bash_parser import BashParser
from scotty.parsing.models import TaskDefinition
from scotty.parsing.parse_result import ParseResult
from scotty.ui import output as out
from scotty.ui.spinner import Spinner

TRACE_MARKER = "ENVOY_TRACE:"

COLORS = ["yellow", "cyan", "magenta", "blue", "green"]


def handle_run(args, file_path: str, dynamic_options: dict[str, str]) -> int:
    config = BashParser().parse(file_path, dynamic_options)

    target = args.task
    tasks = config.resolve_tasks_for_target(target)

    if not tasks:
        _show_available_targets(target, config)
        return 1

    from scotty.ui.prompts import confirm

    for task in tasks:
        if task.confirm is not None:
            if not confirm(task.confirm):
                out.warning("Task cancelled.")
                return 1

    show_summary_only = args.summary
    pretend = args.pretend

    server_colors: dict[str, str] = {}
    color_index = 0
    timings: list[list[str]] = []
    failed = False
    task_start_time = 0.0
    last_traced_command = ""
    pause_requested = False
    spinner = Spinner()
    original_terminal_attrs = None

    def get_server_color(name: str) -> str:
        nonlocal color_index
        if name not in server_colors:
            server_colors[name] = COLORS[color_index % len(COLORS)]
            color_index += 1
        return server_colors[name]

    def format_duration(seconds: float) -> str:
        rounded = round(seconds)
        if rounded < 1:
            return "0s"
        if rounded < 60:
            return f"{rounded}s"
        minutes = rounded // 60
        remaining = rounded % 60
        return f"{minutes}m {remaining}s"

    def truncate(text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 1] + "…"

    def current_local_time() -> str:
        try:
            localtime = os.readlink("/etc/localtime")
            m = re.search(r"zoneinfo/(.+)$", localtime)
            if m:
                import datetime
                import zoneinfo

                tz = zoneinfo.ZoneInfo(m.group(1))
                return datetime.datetime.now(tz).strftime("%H:%M:%S")
        except (OSError, Exception):
            pass

        import datetime

        return datetime.datetime.now().strftime("%H:%M:%S")

    def is_ssh_warning(line: str) -> bool:
        return (
            "Warning: Permanently added" in line
            or "Connection to" in line
            or "Warning: No xauth data" in line
        )

    def is_trace_noise(command: str) -> bool:
        if re.match(r"^[A-Z_][A-Z0-9_]*=", command):
            return True
        if re.match(r"^(echo|printf)\b", command):
            return True
        if re.match(r"^(set|export|local|readonly|declare|trap)\b", command):
            return True
        if re.match(r"^\[{1,2}\s", command) or command.startswith("test "):
            return True
        if command.startswith("sleep "):
            return True
        return False

    def extract_trace_command(line: str) -> str | None:
        pos = line.find(TRACE_MARKER)
        if pos == -1:
            return None
        command = line[pos + len(TRACE_MARKER) :].strip()
        if not command:
            return None
        if is_trace_noise(command):
            return ""
        return command

    def clean_output_line(line: str) -> str:
        if line.startswith("-e "):
            line = line[3:]
        return out.strip_ansi(line)

    def enable_pause_detection() -> None:
        nonlocal original_terminal_attrs
        if not sys.stdin.isatty():
            return
        try:
            import termios

            original_terminal_attrs = termios.tcgetattr(sys.stdin)
            new_attrs = termios.tcgetattr(sys.stdin)
            new_attrs[3] = new_attrs[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(sys.stdin, termios.TCSANOW, new_attrs)
        except (ImportError, termios.error):
            pass

    def disable_pause_detection() -> None:
        if original_terminal_attrs is None:
            return
        try:
            import termios

            termios.tcsetattr(sys.stdin, termios.TCSANOW, original_terminal_attrs)
        except (ImportError, termios.error):
            pass

    def check_for_pause_input() -> None:
        nonlocal pause_requested
        if not sys.stdin.isatty():
            return
        try:
            import select as sel

            ready, _, _ = sel.select([sys.stdin], [], [], 0)
            if ready:
                ch = sys.stdin.read(1)
                if ch in ("p", "P"):
                    pause_requested = True
                    spinner.clear_line()
                    elapsed = format_duration(time.monotonic() - task_start_time)
                    spinner.write_line(elapsed, last_traced_command, pause_requested)
        except Exception:
            pass

    def handle_pause_between_tasks() -> None:
        nonlocal pause_requested
        check_for_pause_input()
        if not pause_requested:
            return

        spinner.clear_line()
        out.writeln()
        out.writeln(
            "  \033[33;1m⏸  Paused\033[0m "
            "\033[38;2;74;85;104mpress Enter to continue, ^C to quit\033[0m"
        )

        while True:
            try:
                import select as sel

                ready, _, _ = sel.select([sys.stdin], [], [], 0.05)
                if ready:
                    ch = sys.stdin.read(1)
                    if ch in ("\n", "\r", " "):
                        break
            except Exception:
                break

        pause_requested = False
        sys.stdout.write("\033[2A\033[2K\033[1B\033[2K\033[1A")
        out.writeln("  \033[32m▶  Resumed\033[0m")
        out.writeln()

    def cleanup() -> None:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        disable_pause_detection()

    def sigint_handler(signum, frame) -> None:
        spinner.clear_line()
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        disable_pause_detection()

        out.writeln()
        t = current_local_time()
        out.writeln(f"  \033[33;1mCancelled.\033[0m \033[90m({t})\033[0m")
        out.writeln()
        sys.exit(130)

    enable_pause_detection()
    signal.signal(signal.SIGINT, sigint_handler)
    atexit.register(cleanup)
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    out.writeln()
    out.writeln(f"  \033[1mRunning {target}\033[0m")
    out.writeln()

    executor = Executor()
    current_step = 0

    def on_task_start(task: TaskDefinition, index: int, total: int) -> None:
        nonlocal task_start_time, last_traced_command, current_step
        handle_pause_between_tasks()

        current_step = index + 1
        task_start_time = time.monotonic()
        last_traced_command = ""

        servers = ", ".join(task.servers)
        parallel_str = " \033[36mparallel\033[0m" if task.parallel else ""

        is_remote = any((srv := config.get_server(s)) and not srv.is_local() for s in task.servers)
        dot = "\033[33m●\033[0m" if is_remote else "\033[34m●\033[0m"

        spinner.clear_line()
        emoji_prefix = f"{task.emoji} " if task.emoji else ""
        out.writeln(
            f"  {dot} {emoji_prefix}\033[1m{task.display_name()}\033[0m "
            f"\033[38;2;74;85;104m[{current_step}/{total}] on {servers}\033[0m{parallel_str}"
        )

    def on_task_output(output_type: str, server_name: str, output_text: str) -> None:
        nonlocal last_traced_command
        check_for_pause_input()
        spinner.clear_line()

        lines = output_text.rstrip().split("\n")
        color = get_server_color(server_name)

        for line in lines:
            if not line.strip():
                continue
            if is_ssh_warning(line):
                continue

            if output_type == "err":
                if TRACE_MARKER in line:
                    command = extract_trace_command(line)
                    if command is not None:
                        if command == "":
                            last_traced_command = ""
                        else:
                            last_traced_command = command
                    continue

            clean_line = clean_output_line(line)
            out.writeln(
                f"  \033[38;2;74;85;104m│\033[0m  {out.styled(server_name, fg=color)}  {clean_line}"
            )

        elapsed = format_duration(time.monotonic() - task_start_time)
        spinner.write_line(elapsed, last_traced_command, pause_requested)

    def on_tick() -> None:
        check_for_pause_input()
        elapsed = format_duration(time.monotonic() - task_start_time)
        spinner.overwrite_line(elapsed, last_traced_command, pause_requested)

    def on_task_complete(task: TaskDefinition, result: TaskResult) -> None:
        nonlocal failed
        spinner.clear_line()

        duration = format_duration(result.duration)
        servers = ", ".join(task.servers)

        if pretend:
            for output_text in result.outputs.values():
                out.writeln(output_text)
            timings.append(
                [task.display_name_with_emoji(), servers, "-", "\033[38;2;74;85;104mpretend\033[0m"]
            )
            out.writeln()
            return

        if result.succeeded():
            out.writeln(
                f"  \033[32m✓ Task done:\033[0m {task.display_name()} "
                f"\033[38;2;74;85;104m{duration}\033[0m"
            )
            timings.append([task.display_name_with_emoji(), servers, duration, "\033[32mOK\033[0m"])
            out.writeln()
            return

        failed = True
        out.writeln(
            f"  \033[31m✗ Task failed:\033[0m {task.display_name()} "
            f"\033[38;2;74;85;104m{duration}\033[0m"
        )

        if show_summary_only:
            out.writeln()
            for host_name, output_text in result.outputs.items():
                for line in output_text.rstrip().split("\n"):
                    if not line.strip():
                        continue
                    if is_ssh_warning(line):
                        continue
                    if TRACE_MARKER in line:
                        continue
                    out.writeln(f"    \033[38;2;74;85;104m{host_name}\033[0m  {line}")

        if result.failed_host:
            out.writeln(f"  \033[31m  └ failed on {result.failed_host}\033[0m")

        timings.append([task.display_name_with_emoji(), servers, duration, "\033[31mFAILED\033[0m"])
        out.writeln()

    results = executor.run(
        target=target,
        config=config,
        env=dynamic_options,
        continue_on_error=args.continue_on_error,
        pretend=pretend,
        on_task_start=on_task_start,
        on_task_output=None if show_summary_only else on_task_output,
        on_task_complete=on_task_complete,
        on_tick=on_tick,
    )

    spinner.clear_line()
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    disable_pause_detection()

    # Summary
    if results:
        out.table(["Task", "Server", "Duration", "Status"], timings)

        total_duration = format_duration(sum(r.duration for r in results.values()))
        total_count = len(results)

        if not failed:
            t = current_local_time()
            out.writeln(
                f"  \033[32;1m✓ All {total_count} tasks completed in {total_duration}\033[0m "
                f"\033[90m({t})\033[0m"
            )
            out.writeln()
        else:
            failed_task = next((name for name, r in results.items() if not r.succeeded()), None)
            t = current_local_time()
            out.writeln(f"  \033[31;1m✗ Failed at {failed_task}\033[0m \033[90m({t})\033[0m")
            out.writeln()

    return 1 if failed else 0


def _show_available_targets(target: str, config: ParseResult) -> None:
    out.error(f'Task or macro "{target}" is not defined.')

    available = config.available_targets()

    if available["tasks"]:
        out.writeln()
        out.info("Available tasks:")
        for name in available["tasks"]:
            out.writeln(f"  - {name}")

    if available["macros"]:
        out.writeln()
        out.info("Available macros:")
        for name in available["macros"]:
            out.writeln(f"  - {name}")
