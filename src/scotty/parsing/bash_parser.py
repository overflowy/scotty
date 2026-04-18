from __future__ import annotations

import re
import textwrap


def _escape_shell_arg(value: str) -> str:
    """PHP's escapeshellarg: always single-quote-wrap, escape embedded quotes."""
    return "'" + value.replace("'", "'\\''") + "'"

from scotty.parsing.models import (
    HookDefinition,
    HookType,
    MacroDefinition,
    ServerDefinition,
    TaskDefinition,
)
from scotty.parsing.parse_result import ParseResult


class BashParser:
    def parse(self, file_path: str, data: dict[str, str] | None = None) -> ParseResult:
        with open(file_path) as f:
            content = f.read()

        return ParseResult(
            servers=self._parse_servers(content),
            tasks=self._parse_tasks(content),
            macros=self._parse_macros(content),
            hooks=self._parse_hooks(content),
            variable_preamble=self._parse_variables(content, data or {}),
        )

    def _parse_servers(self, content: str) -> dict[str, ServerDefinition]:
        servers: dict[str, ServerDefinition] = {}

        m = re.search(r"^#\s*@servers\s+(.+)$", content, re.MULTILINE)
        if m:
            for pair in re.finditer(r"([\w-]+)=(\S+)", m.group(1)):
                name = pair.group(1)
                servers[name] = ServerDefinition(name, pair.group(2))

        return servers

    def _parse_macros(self, content: str) -> dict[str, MacroDefinition]:
        macros: dict[str, MacroDefinition] = {}
        self._parse_single_line_macros(content, macros)
        self._parse_multi_line_macros(content, macros)
        return macros

    def _parse_single_line_macros(self, content: str, macros: dict[str, MacroDefinition]) -> None:
        for m in re.finditer(r"^#\s*@macro\s+(\w[\w-]*)\s+(.+)$", content, re.MULTILINE):
            name = m.group(1)
            tasks = re.split(r"\s+", m.group(2).strip())
            macros[name] = MacroDefinition(name, tasks)

    def _parse_multi_line_macros(self, content: str, macros: dict[str, MacroDefinition]) -> None:
        pattern = r"^#\s*@macro\s+(\w[\w-]*)\s*$\n((?:#\s+\w[\w-]*\s*\n)+)#\s*@endmacro"

        for m in re.finditer(pattern, content, re.MULTILINE):
            name = m.group(1)
            task_lines = m.group(2).strip().split("\n")
            tasks = [line.strip().lstrip("#").strip() for line in task_lines]
            tasks = [t for t in tasks if t]
            macros[name] = MacroDefinition(name, tasks)

    def _parse_tasks(self, content: str) -> dict[str, TaskDefinition]:
        tasks: dict[str, TaskDefinition] = {}

        pattern = r"^#\s*@task\s+(.+)$\n(\w+)\(\)\s*\{"

        for m in re.finditer(pattern, content, re.MULTILINE):
            options = m.group(1)
            name = m.group(2)
            body_start = m.end()

            script = self._extract_function_body(content, body_start)
            servers = self._parse_task_servers(options)
            is_parallel = "parallel" in options
            confirm_message = self._parse_task_confirm(options)

            tasks[name] = TaskDefinition(
                name=name,
                script=self._dedent(script),
                servers=servers,
                parallel=is_parallel,
                confirm=confirm_message,
                emoji=self._parse_task_emoji(options),
            )

        return tasks

    def _parse_hooks(self, content: str) -> list[HookDefinition]:
        hooks: list[HookDefinition] = []

        for hook_type in HookType:
            pattern = rf"^#\s*@{hook_type.value}\s*$\n(\w+)\(\)\s*\{{"

            for m in re.finditer(pattern, content, re.MULTILINE):
                body_start = m.end()
                script = self._extract_function_body(content, body_start)
                hooks.append(HookDefinition(type=hook_type, script=self._dedent(script)))

        return hooks

    def _parse_variables(self, content: str, cli_data: dict[str, str]) -> str:
        lines: list[str] = []

        for line in content.split("\n"):
            trimmed = line.strip()

            if re.match(r"^\w+\(\)\s*\{", trimmed):
                break

            if trimmed == "" or trimmed.startswith("#") or trimmed.startswith("#!/"):
                continue

            if re.match(r"^[A-Z_][A-Z0-9_]*=", trimmed):
                lines.append(line)

        helper_functions = self._extract_helper_functions(content)

        for key, value in cli_data.items():
            upper_key = key.upper()
            lines.append(f"{upper_key}={_escape_shell_arg(value)}")

        preamble = "\n".join(lines)

        if helper_functions:
            preamble += f"\n{helper_functions}"

        return preamble

    def _extract_helper_functions(self, content: str) -> str:
        annotated = self._annotated_function_names(content)
        functions: list[str] = []

        for m in re.finditer(r"^(\w+)\(\)\s*\{", content, re.MULTILINE):
            function_name = m.group(1)
            if function_name in annotated:
                continue

            body_start = m.end()
            body = self._extract_function_body(content, body_start)
            functions.append(f"{function_name}() {{\n{body}\n}}")

        return "\n\n".join(functions)

    def _annotated_function_names(self, content: str) -> set[str]:
        names: set[str] = set()

        for m in re.finditer(r"^#\s*@task\s+.+$\n(\w+)\(\)", content, re.MULTILINE):
            names.add(m.group(1))

        for hook_type in HookType:
            pattern = rf"^#\s*@{hook_type.value}\s*$\n(\w+)\(\)"
            for m in re.finditer(pattern, content, re.MULTILINE):
                names.add(m.group(1))

        return names

    def _extract_function_body(self, content: str, start_offset: int) -> str:
        depth = 1
        position = start_offset
        length = len(content)
        in_single_quote = False
        in_double_quote = False

        while position < length and depth > 0:
            char = content[position]

            if char == "\\":
                if in_single_quote or in_double_quote:
                    position += 2
                    continue

            if char == "'":
                if not in_double_quote:
                    in_single_quote = not in_single_quote
            elif char == '"':
                if not in_single_quote:
                    in_double_quote = not in_double_quote
            elif not in_single_quote and not in_double_quote:
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1

            if depth > 0:
                position += 1

        return content[start_offset:position]

    def _parse_task_servers(self, options: str) -> list[str]:
        m = re.search(r"on:(\S+)", options)
        if m:
            return m.group(1).split(",")
        return []

    def _parse_task_confirm(self, options: str) -> str | None:
        m = re.search(r'confirm="([^"]+)"', options)
        if m:
            return m.group(1)
        return None

    def _parse_task_emoji(self, options: str) -> str | None:
        m = re.search(r"emoji:(\S+)", options)
        if m:
            return m.group(1)
        return None

    def _dedent(self, text: str) -> str:
        return textwrap.dedent(text).strip()
