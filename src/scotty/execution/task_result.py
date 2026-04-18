from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskResult:
    exit_code: int
    outputs: dict[str, str] = field(default_factory=dict)
    duration: float = 0.0
    failed_host: str | None = None

    def succeeded(self) -> bool:
        return self.exit_code == 0
