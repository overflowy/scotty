from __future__ import annotations

import argparse
import os
import re
import sys

from scotty.ui.banner import render_banner

SCOTTY_FILENAMES = [
    "Scotty.sh",
    "scotty.sh",
    "Envoy.sh",
    "envoy.sh",
]


def resolve_file_path(path_opt: str | None = None, conf_opt: str | None = None) -> str | None:
    if path_opt:
        return path_opt if os.path.exists(path_opt) else None

    if conf_opt:
        return conf_opt if os.path.exists(conf_opt) else None

    for candidate in SCOTTY_FILENAMES:
        if os.path.exists(candidate):
            return candidate

    return None


def resolve_file_path_or_fail(
    path_opt: str | None = None, conf_opt: str | None = None
) -> str | None:
    file_path = resolve_file_path(path_opt, conf_opt)

    if file_path is not None:
        return file_path

    from scotty.ui import output as out

    out.error("No Scotty file found. Checked for:")
    for candidate in SCOTTY_FILENAMES:
        out.writeln(f"  - {candidate}")
    out.writeln()
    out.writeln("  Run `scotty init` to create one.")

    return None


def gather_dynamic_options() -> dict[str, str]:
    data: dict[str, str] = {}
    known_options = {"continue", "pretend", "path", "conf", "summary"}

    for argument in sys.argv:
        m = re.match(r"^--([a-zA-Z][\w-]*)=(.+)$", argument)
        if not m:
            continue

        key = m.group(1)
        if key in known_options:
            continue

        value = m.group(2)
        data[key] = value

        # camelCase variant
        camel = re.sub(r"-(\w)", lambda x: x.group(1).upper(), key)
        data[camel] = value

        # snake_case variant
        snake = key.replace("-", "_")
        data[snake] = value

    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scotty",
        description="Run tasks on remote servers",
        add_help=True,
    )

    subparsers = parser.add_subparsers(dest="command")

    # run
    run_parser = subparsers.add_parser("run", help="Run a task or macro")
    run_parser.add_argument("task", help="The task or macro to run")
    run_parser.add_argument(
        "--continue", dest="continue_on_error", action="store_true", help="Continue on failure"
    )
    run_parser.add_argument(
        "--pretend", action="store_true", help="Dump the script instead of running it"
    )
    run_parser.add_argument("--path", default=None, help="Path to the Scotty file")
    run_parser.add_argument("--conf", default=None, help="Scotty filename")
    run_parser.add_argument(
        "--summary", action="store_true", help="Only show task results, hide output"
    )

    # tasks
    tasks_parser = subparsers.add_parser("tasks", help="List all available tasks and macros")
    tasks_parser.add_argument("--path", default=None, help="Path to the Scotty file")
    tasks_parser.add_argument("--conf", default=None, help="Scotty filename")

    # init
    subparsers.add_parser("init", help="Create a new Scotty file")

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Validate environment and configuration")
    doctor_parser.add_argument("--path", default=None, help="Path to the Scotty file")
    doctor_parser.add_argument("--conf", default=None, help="Scotty filename")

    # ssh
    ssh_parser = subparsers.add_parser("ssh", help="SSH into a defined server")
    ssh_parser.add_argument("name", nargs="?", default=None, help="The server to connect to")
    ssh_parser.add_argument("--path", default=None, help="Path to the Scotty file")
    ssh_parser.add_argument("--conf", default=None, help="Scotty filename")

    # Use parse_known_args to allow dynamic --key=value options
    args, _ = parser.parse_known_args()

    if args.command is None:
        render_banner()
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        from scotty.commands.init_cmd import handle_init

        sys.exit(handle_init(args))

    if args.command == "run":
        file_path = resolve_file_path_or_fail(args.path, args.conf)
        if file_path is None:
            sys.exit(1)

        from scotty.commands.run import handle_run

        sys.exit(handle_run(args, file_path, gather_dynamic_options()))

    if args.command == "tasks":
        file_path = resolve_file_path_or_fail(args.path, args.conf)
        if file_path is None:
            sys.exit(1)

        from scotty.commands.tasks import handle_tasks

        sys.exit(handle_tasks(args, file_path))

    if args.command == "doctor":
        file_path = resolve_file_path(getattr(args, "path", None), getattr(args, "conf", None))

        from scotty.commands.doctor import handle_doctor

        sys.exit(handle_doctor(args, file_path))

    if args.command == "ssh":
        file_path = resolve_file_path_or_fail(args.path, args.conf)
        if file_path is None:
            sys.exit(1)

        from scotty.commands.ssh import handle_ssh

        sys.exit(handle_ssh(args, file_path))
