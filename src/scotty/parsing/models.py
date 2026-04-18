from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field


class HookType(str, enum.Enum):
    BEFORE = "before"
    AFTER = "after"
    SUCCESS = "success"
    ERROR = "error"
    FINISHED = "finished"


@dataclass
class ServerDefinition:
    name: str
    hosts: list[str]

    LOCAL_HOSTS = ("127.0.0.1", "localhost", "local")

    def __init__(self, name: str, host: str | list[str]) -> None:
        self.name = name
        self.hosts = list(host) if isinstance(host, list) else [host]

    def is_local(self) -> bool:
        return len(self.hosts) == 1 and self.hosts[0] in self.LOCAL_HOSTS

    @staticmethod
    def is_local_host(host: str) -> bool:
        return host in ServerDefinition.LOCAL_HOSTS


@dataclass
class TaskDefinition:
    name: str
    script: str
    servers: list[str] = field(default_factory=list)
    parallel: bool = False
    confirm: str | None = None
    emoji: str | None = None

    def display_name(self) -> str:
        humanized = re.sub(r"([a-z])([A-Z])", r"\1 \2", self.name)
        humanized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", humanized)
        humanized = humanized.replace("-", " ").replace("_", " ")
        return humanized[0].upper() + humanized[1:].lower() if humanized else ""

    def display_name_with_emoji(self) -> str:
        if self.emoji is not None:
            return f"{self.emoji}  {self.display_name()}"
        return self.display_name()


@dataclass
class MacroDefinition:
    name: str
    tasks: list[str]


@dataclass
class HookDefinition:
    type: HookType
    script: str
