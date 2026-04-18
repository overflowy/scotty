from __future__ import annotations

from dataclasses import dataclass, field

from scotty.parsing.models import (
    HookDefinition,
    HookType,
    MacroDefinition,
    ServerDefinition,
    TaskDefinition,
)


@dataclass
class ParseResult:
    servers: dict[str, ServerDefinition] = field(default_factory=dict)
    tasks: dict[str, TaskDefinition] = field(default_factory=dict)
    macros: dict[str, MacroDefinition] = field(default_factory=dict)
    hooks: list[HookDefinition] = field(default_factory=list)
    variable_preamble: str = ""

    def get_task(self, name: str) -> TaskDefinition | None:
        return self.tasks.get(name)

    def get_macro(self, name: str) -> MacroDefinition | None:
        return self.macros.get(name)

    def get_server(self, name: str) -> ServerDefinition | None:
        return self.servers.get(name)

    def resolve_tasks_for_target(self, name: str) -> list[TaskDefinition]:
        macro = self.get_macro(name)
        if macro is not None:
            return [self.tasks[task_name] for task_name in macro.tasks]

        task = self.get_task(name)
        if task is not None:
            return [task]

        return []

    def get_hooks(self, hook_type: HookType) -> list[HookDefinition]:
        return [h for h in self.hooks if h.type == hook_type]

    def available_targets(self) -> dict[str, list[str]]:
        return {
            "tasks": list(self.tasks.keys()),
            "macros": list(self.macros.keys()),
        }
