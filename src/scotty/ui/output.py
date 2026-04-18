from __future__ import annotations

import re
import sys


def styled(text: str, *, fg: str = "", bold: bool = False) -> str:
    codes = []
    if bold:
        codes.append("1")
    if fg:
        if fg.startswith("#"):
            r, g, b = int(fg[1:3], 16), int(fg[3:5], 16), int(fg[5:7], 16)
            codes.append(f"38;2;{r};{g};{b}")
        else:
            color_map = {
                "red": "31", "green": "32", "yellow": "33",
                "blue": "34", "magenta": "35", "cyan": "36",
                "gray": "90",
            }
            if fg in color_map:
                codes.append(color_map[fg])
    if not codes:
        return text
    return f"\033[{';'.join(codes)}m{text}\033[0m"


def strip_ansi(text: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", text)


def write(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def writeln(text: str = "") -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def error(text: str) -> None:
    writeln(styled(f"  ERROR  {text}", fg="red", bold=True))


def info(text: str) -> None:
    writeln(styled(f"  {text}", fg="blue"))


def warning(text: str) -> None:
    writeln(styled(f"  {text}", fg="yellow"))


def table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        return

    all_rows = [headers] + rows

    col_widths = [0] * len(headers)
    for row in all_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(strip_ansi(cell)))

    writeln()

    # Header
    header_parts = []
    for i, header in enumerate(headers):
        header_parts.append(f" {header:<{col_widths[i]}} ")
    writeln("  " + styled("|".join(header_parts), bold=True))

    # Separator
    sep_parts = ["-" * (w + 2) for w in col_widths]
    writeln("  " + "+".join(sep_parts))

    # Rows
    for row in rows:
        row_parts = []
        for i, cell in enumerate(row):
            padding = col_widths[i] - len(strip_ansi(cell))
            row_parts.append(f" {cell}{' ' * padding} ")
        writeln("  " + "|".join(row_parts))

    writeln()
