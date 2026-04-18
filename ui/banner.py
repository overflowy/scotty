from __future__ import annotations

import sys


def render_banner() -> None:
    lines = [
        "  ███████╗  ██████╗  ██████╗  ████████╗ ████████╗ ██╗   ██╗",
        "  ██╔════╝ ██╔════╝ ██╔═══██╗ ╚══██╔══╝ ╚══██╔══╝ ╚██╗ ██╔╝",
        "  ███████╗ ██║      ██║   ██║    ██║       ██║      ╚████╔╝ ",
        "  ╚════██║ ██║      ██║   ██║    ██║       ██║       ╚██╔╝  ",
        "  ███████║ ╚██████╗ ╚██████╔╝    ██║       ██║        ██║   ",
        "  ╚══════╝  ╚═════╝  ╚═════╝     ╚═╝       ╚═╝        ╚═╝   ",
    ]

    gradient = [39, 38, 44, 43, 49, 48]

    sys.stdout.write("\n")

    for index, line in enumerate(lines):
        sys.stdout.write(f"\033[38;5;{gradient[index]}m{line}\033[0m\n")

    sys.stdout.write("\n")

    tagline = " ✦ Run tasks on remote servers :: spatie.be/docs/scotty ✦ "
    sys.stdout.write(f"\033[48;5;{gradient[0]}m\033[30m\033[1m{tagline}\033[0m\n")

    sys.stdout.write("\n")
    sys.stdout.flush()
