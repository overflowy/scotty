from __future__ import annotations

import re

from scotty.parsing.models import (
    HookDefinition,
    HookType,
    MacroDefinition,
    ServerDefinition,
    TaskDefinition,
)
from scotty.parsing.parse_result import ParseResult


class BladeParser:
    def parse(self, file_path: str, data: dict[str, str] | None = None) -> ParseResult:
        with open(file_path) as f:
            content = f.read()

        setup_vars = self._parse_setup(content)
        if data:
            setup_vars.update(data)

        servers = self._parse_servers(content, setup_vars)
        tasks = self._parse_tasks(content, setup_vars, servers)
        macros = self._parse_macros(content)
        hooks = self._parse_hooks(content, setup_vars)

        return ParseResult(
            servers=servers,
            tasks=tasks,
            macros=macros,
            hooks=hooks,
        )

    def _parse_setup(self, content: str) -> dict[str, str | list[str]]:
        variables: dict[str, str | list[str]] = {}

        m = re.search(r"@setup\s*\n(.*?)@endsetup", content, re.DOTALL)
        if not m:
            return variables

        setup_body = m.group(1)

        self._check_unsupported_php(setup_body)

        # Parse array assignments: $var = ['val1', 'val2'];
        for arr_m in re.finditer(
            r"\$(\w+)\s*=\s*\[(.*?)\]\s*;", setup_body, re.DOTALL
        ):
            var_name = arr_m.group(1)
            array_content = arr_m.group(2)
            items = re.findall(r"'([^']*)'", array_content)
            variables[var_name] = items

        # Parse simple string assignments: $var = 'value';
        for str_m in re.finditer(r"\$(\w+)\s*=\s*'([^']*)'\s*;", setup_body):
            var_name = str_m.group(1)
            if var_name not in variables:
                variables[var_name] = str_m.group(2)

        return variables

    def _check_unsupported_php(self, setup_body: str) -> None:
        if re.search(r"\b(function\s+\w+|if\s*\(|foreach\s*\(|while\s*\()", setup_body):
            raise ValueError(
                "Complex PHP in @setup is not supported. "
                "Use Scotty.sh format for complex configurations."
            )

    def _parse_servers(
        self, content: str, setup_vars: dict[str, str | list[str]]
    ) -> dict[str, ServerDefinition]:
        servers: dict[str, ServerDefinition] = {}

        m = re.search(r"@servers\(\[(.*?)\]\)", content, re.DOTALL)
        if not m:
            return servers

        server_block = m.group(1)

        for entry in re.finditer(r"'(\w[\w-]*)'\s*=>\s*(\$\w+|'[^']*')", server_block):
            name = entry.group(1)
            value = entry.group(2)

            if value.startswith("$"):
                var_name = value[1:]
                resolved = setup_vars.get(var_name)
                if resolved is None:
                    raise ValueError(f"Undefined variable ${var_name} in @servers")
                host = resolved
            else:
                host = value.strip("'")

            servers[name] = ServerDefinition(name=name, host=host)

        return servers

    def _parse_tasks(
        self,
        content: str,
        setup_vars: dict[str, str | list[str]],
        servers: dict[str, ServerDefinition],
    ) -> dict[str, TaskDefinition]:
        tasks: dict[str, TaskDefinition] = {}

        pattern = r"@task\(\s*'([^']+)'\s*(?:,\s*\[(.*?)\])?\s*\)\s*\n(.*?)@endtask"

        for m in re.finditer(pattern, content, re.DOTALL):
            name = m.group(1)
            options_str = m.group(2) or ""
            body = m.group(3)

            options = self._parse_task_options(options_str)
            server_names = options.get("on", list(servers.keys()))
            if isinstance(server_names, str):
                server_names = [server_names]

            script = self._interpolate(body.strip(), setup_vars)
            script = self._trim_lines(script)

            tasks[name] = TaskDefinition(
                name=name,
                script=script,
                servers=server_names,
                parallel=options.get("parallel", False),
                confirm=options.get("confirm"),
                emoji=options.get("emoji"),
            )

        return tasks

    def _parse_task_options(self, options_str: str) -> dict:
        options: dict = {}

        # Parse 'on' => 'value' or 'on' => ['v1', 'v2']
        on_m = re.search(r"'on'\s*=>\s*(\[.*?\]|'[^']*')", options_str, re.DOTALL)
        if on_m:
            on_val = on_m.group(1)
            if on_val.startswith("["):
                options["on"] = re.findall(r"'([^']*)'", on_val)
            else:
                options["on"] = on_val.strip("'")

        # Parse 'parallel' => true
        if re.search(r"'parallel'\s*=>\s*true", options_str):
            options["parallel"] = True

        # Parse 'confirm' => 'message'
        confirm_m = re.search(r"'confirm'\s*=>\s*'([^']*)'", options_str)
        if confirm_m:
            options["confirm"] = confirm_m.group(1)

        # Parse 'emoji' => 'value'
        emoji_m = re.search(r"'emoji'\s*=>\s*'([^']*)'", options_str)
        if emoji_m:
            options["emoji"] = emoji_m.group(1)

        return options

    def _parse_macros(self, content: str) -> dict[str, MacroDefinition]:
        macros: dict[str, MacroDefinition] = {}

        # @macro('name') or @story('name')
        for tag in ("macro", "story"):
            end_tag = f"end{tag}"
            pattern = rf"@{tag}\(\s*'([^']+)'\s*\)\s*\n(.*?)@{end_tag}"

            for m in re.finditer(pattern, content, re.DOTALL):
                name = m.group(1)
                body = m.group(2).strip()
                tasks = [line.strip() for line in body.split("\n")]
                tasks = [t for t in tasks if t]
                macros[name] = MacroDefinition(name=name, tasks=tasks)

        return macros

    def _parse_hooks(
        self, content: str, setup_vars: dict[str, str | list[str]]
    ) -> list[HookDefinition]:
        hooks: list[HookDefinition] = []

        hook_tags = {
            HookType.BEFORE: ("before", "endbefore"),
            HookType.AFTER: ("after", "endafter"),
            HookType.SUCCESS: ("success", "endsuccess"),
            HookType.ERROR: ("error", "enderror"),
            HookType.FINISHED: ("finished", "endfinished"),
        }

        for hook_type, (start_tag, end_tag) in hook_tags.items():
            pattern = rf"@{start_tag}\s*\n(.*?)@{end_tag}"
            for m in re.finditer(pattern, content, re.DOTALL):
                script = self._interpolate(m.group(1).strip(), setup_vars)
                hooks.append(HookDefinition(type=hook_type, script=script))

        return hooks

    def _interpolate(self, text: str, variables: dict[str, str | list[str]]) -> str:
        def replace_var(m: re.Match) -> str:
            var_name = m.group(1).strip()
            val = variables.get(var_name)
            if val is None:
                return m.group(0)
            if isinstance(val, list):
                return " ".join(val)
            return str(val)

        return re.sub(r"\{\{\s*\$(\w+)\s*\}\}", replace_var, text)

    def _trim_lines(self, text: str) -> str:
        lines = text.split("\n")
        return "\n".join(line.strip() for line in lines)

    def _check_unsupported_directives(self, content: str) -> None:
        unsupported = ["@if", "@foreach", "@unless", "@import", "@include"]
        for directive in unsupported:
            if directive in content:
                raise ValueError(
                    f"{directive} is not supported. "
                    "Use Scotty.sh format for complex configurations."
                )
