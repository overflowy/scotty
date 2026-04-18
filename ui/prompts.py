from __future__ import annotations

import sys


def select(label: str, options: dict[str, str] | list[str], default: str | None = None) -> str:
    if isinstance(options, list):
        options = {opt: opt for opt in options}

    keys = list(options.keys())
    labels = list(options.values())

    print(f"\n  {label}")

    for i, (key, display) in enumerate(options.items()):
        marker = ">" if key == default else " "
        print(f"  {marker} [{i + 1}] {display}")

    while True:
        try:
            choice = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                return keys[idx]

        if choice in keys:
            return choice

        print("  Invalid choice. Try again.")


def confirm(label: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"

    try:
        answer = input(f"  {label} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    if answer == "":
        return default

    return answer in ("y", "yes")


def text(label: str, placeholder: str = "", required: bool = False) -> str:
    hint = f" ({placeholder})" if placeholder else ""

    while True:
        try:
            value = input(f"  {label}{hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)

        if required and not value:
            print("  This field is required.")
            continue

        return value
