from __future__ import annotations

import sys

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
HINTS = "  \033[38;2;74;85;104mp pause  ^C quit\033[0m"


class Spinner:
    def __init__(self) -> None:
        self.index = 0
        self.visible = False

    def frame(self) -> str:
        f = SPINNER_FRAMES[self.index % len(SPINNER_FRAMES)]
        self.index += 1
        return f

    def write_line(
        self,
        elapsed: str,
        command: str = "",
        pause_requested: bool = False,
    ) -> None:
        line = self._build_content(elapsed, command, pause_requested)

        sys.stdout.write(f"{line}\n\n{HINTS}\n")
        sys.stdout.flush()
        self.visible = True

    def overwrite_line(
        self,
        elapsed: str,
        command: str = "",
        pause_requested: bool = False,
    ) -> None:
        if not self.visible:
            self.write_line(elapsed, command, pause_requested)
            return

        line = self._build_content(elapsed, command, pause_requested)

        sys.stdout.write(f"\033[3A\r{line}\033[K\n\n{HINTS}\033[K\n")
        sys.stdout.flush()

    def clear_line(self) -> None:
        if not self.visible:
            return

        sys.stdout.write("\033[1A\033[2K\033[1A\033[2K\033[1A\033[2K")
        sys.stdout.flush()
        self.visible = False

    def _build_content(
        self,
        elapsed: str,
        command: str = "",
        pause_requested: bool = False,
    ) -> str:
        frame = self.frame()

        line = (
            f"  \033[38;2;74;85;104m│\033[0m  "
            f"\033[34m{frame}\033[0m  "
            f"\033[38;2;74;85;104m{elapsed}\033[0m"
        )

        if command:
            line += f"  \033[38;2;74;85;104m▸ {command}\033[0m"

        if pause_requested:
            line += "  \033[33m⏸ pausing after this task\033[0m"

        return line
