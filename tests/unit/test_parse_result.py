from __future__ import annotations

import pytest

from scotty.parsing.models import (
    HookDefinition,
    HookType,
    MacroDefinition,
    ServerDefinition,
    TaskDefinition,
)
from scotty.parsing.parse_result import ParseResult


@pytest.fixture
def result() -> ParseResult:
    return ParseResult(
        servers={
            "local": ServerDefinition("local", "127.0.0.1"),
            "remote": ServerDefinition("remote", "forge@1.1.1.1"),
        },
        tasks={
            "pull": TaskDefinition("pull", "git pull origin main", ["remote"]),
            "build": TaskDefinition("build", "npm run build", ["remote"]),
            "restart": TaskDefinition("restart", "sudo systemctl restart nginx", ["remote"]),
        },
        macros={
            "deploy": MacroDefinition("deploy", ["pull", "build"]),
        },
        hooks=[
            HookDefinition(HookType.BEFORE, 'echo "starting"'),
            HookDefinition(HookType.AFTER, 'echo "done"'),
            HookDefinition(HookType.SUCCESS, 'echo "success"'),
        ],
    )


def test_get_task_by_name(result):
    task = result.get_task("pull")
    assert task is not None
    assert task.name == "pull"


def test_get_task_returns_none_for_unknown(result):
    assert result.get_task("nonexistent") is None


def test_get_macro_by_name(result):
    macro = result.get_macro("deploy")
    assert macro is not None
    assert macro.name == "deploy"


def test_get_macro_returns_none_for_unknown(result):
    assert result.get_macro("nonexistent") is None


def test_get_server_by_name(result):
    server = result.get_server("remote")
    assert server is not None
    assert server.hosts == ["forge@1.1.1.1"]


def test_get_server_returns_none_for_unknown(result):
    assert result.get_server("nonexistent") is None


def test_resolve_tasks_for_macro_name(result):
    tasks = result.resolve_tasks_for_target("deploy")
    assert [t.name for t in tasks] == ["pull", "build"]


def test_resolve_tasks_for_single_task_name(result):
    tasks = result.resolve_tasks_for_target("restart")
    assert [t.name for t in tasks] == ["restart"]


def test_resolve_tasks_for_unknown_returns_empty(result):
    assert result.resolve_tasks_for_target("nonexistent") == []


def test_filter_hooks_by_type(result):
    assert len(result.get_hooks(HookType.BEFORE)) == 1
    assert len(result.get_hooks(HookType.SUCCESS)) == 1
    assert result.get_hooks(HookType.ERROR) == []


def test_servers_with_multiple_hosts():
    result = ParseResult(
        servers={
            "web": ServerDefinition("web", ["forge@1.1.1.1", "forge@2.2.2.2"]),
            "local": ServerDefinition("local", "127.0.0.1"),
        },
    )

    assert result.get_server("web").hosts == ["forge@1.1.1.1", "forge@2.2.2.2"]
    assert result.get_server("local").hosts == ["127.0.0.1"]
    assert result.get_server("local").is_local() is True
    assert result.get_server("web").is_local() is False


def test_available_targets_lists_tasks_and_macros(result):
    targets = result.available_targets()
    assert targets["tasks"] == ["pull", "build", "restart"]
    assert targets["macros"] == ["deploy"]


def test_missing_macro_tasks_reports_undefined_references():
    result = ParseResult(
        tasks={"pull": TaskDefinition("pull", "", ["remote"])},
        macros={"deploy": MacroDefinition("deploy", ["pull", "ghost", "alsoGhost"])},
    )
    assert result.missing_macro_tasks("deploy") == ["ghost", "alsoGhost"]


def test_missing_macro_tasks_returns_empty_for_valid_macro(result):
    assert result.missing_macro_tasks("deploy") == []


def test_missing_macro_tasks_returns_empty_for_unknown_target(result):
    assert result.missing_macro_tasks("nonexistent") == []


def test_resolve_tasks_for_target_skips_missing_macro_entries():
    result = ParseResult(
        tasks={"pull": TaskDefinition("pull", "", ["remote"])},
        macros={"deploy": MacroDefinition("deploy", ["pull", "ghost"])},
    )
    tasks = result.resolve_tasks_for_target("deploy")
    assert [t.name for t in tasks] == ["pull"]
