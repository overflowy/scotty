from __future__ import annotations

from scotty.parsing.bash_parser import BashParser
from scotty.ui import output as out


def handle_tasks(args, file_path: str) -> int:
    config = BashParser().parse(file_path)
    available = config.available_targets()

    out.writeln()

    if available["macros"]:
        out.writeln("  \033[1mMacros\033[0m")
        out.writeln()

        for name in available["macros"]:
            macro = config.get_macro(name)
            task_list = []
            for task_name in macro.tasks:
                task = config.get_task(task_name)
                if task is None:
                    task_list.append(task_name)
                else:
                    task_list.append(task.display_name_with_emoji())

            out.writeln(f"  \033[32m{name}\033[0m")
            for i, task_display in enumerate(task_list):
                out.writeln(f"    \033[38;2;74;85;104m{i + 1}.\033[0m {task_display}")
            out.writeln()

    if available["tasks"]:
        out.writeln("  \033[1mTasks\033[0m")
        out.writeln()

        for name in available["tasks"]:
            task = config.get_task(name)
            servers = ", ".join(task.servers)
            parallel = " \033[36mparallel\033[0m" if task.parallel else ""
            display_name = task.display_name_with_emoji()

            out.writeln(f"  {display_name}  \033[38;2;74;85;104mon {servers}\033[0m{parallel}")

        out.writeln()

    return 0
