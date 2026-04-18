from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scotty.parsing.bash_parser import BashParser
from scotty.parsing.models import HookType


@pytest.fixture
def parser() -> BashParser:
    return BashParser()


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(textwrap.dedent(content))
    return str(path)


def test_parses_servers(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    assert len(result.servers) == 3
    assert result.servers["local"].name == "local"
    assert result.servers["local"].hosts == ["127.0.0.1"]
    assert result.servers["production"].name == "production"
    assert result.servers["production"].hosts == ["forge@production.example.com"]
    assert result.servers["staging"].name == "staging"
    assert result.servers["staging"].hosts == ["forge@staging.example.com"]


def test_parses_server_names_with_hyphens(parser, tmp_path):
    path = _write(
        tmp_path,
        "dashed_servers.sh",
        """\
        # @servers local=127.0.0.1 web-1=deployer@web-1.example.com web-2=deployer@web-2.example.com

        # @task on:web-1,web-2
        restart() {
            echo restarting
        }
        """,
    )

    result = parser.parse(path)

    assert set(result.servers.keys()) == {"local", "web-1", "web-2"}
    assert result.servers["web-1"].hosts == ["deployer@web-1.example.com"]
    assert result.servers["web-2"].hosts == ["deployer@web-2.example.com"]


def test_parses_single_line_macros(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    assert len(result.macros) == 2
    assert result.macros["deploy"].name == "deploy"
    assert result.macros["deploy"].tasks == ["pull", "migrate"]
    assert result.macros["fullDeploy"].name == "fullDeploy"
    assert result.macros["fullDeploy"].tasks == ["pull", "migrate", "clearCache"]


def test_parses_multi_line_macros(parser, tmp_path):
    path = _write(
        tmp_path,
        "multiline.sh",
        """\
        # @servers local=127.0.0.1

        # @macro deploy
        #   pullCode
        #   runComposer
        #   clearCaches
        # @endmacro

        # @task on:local
        pullCode() {
            echo "pulling"
        }

        # @task on:local
        runComposer() {
            echo "composing"
        }

        # @task on:local
        clearCaches() {
            echo "clearing"
        }
        """,
    )

    result = parser.parse(path)

    assert len(result.macros) == 1
    assert result.macros["deploy"].tasks == ["pullCode", "runComposer", "clearCaches"]


def test_supports_single_and_multi_line_macros_together(parser, tmp_path):
    path = _write(
        tmp_path,
        "mixed.sh",
        """\
        # @servers local=127.0.0.1
        # @macro quick taskA taskB

        # @macro full
        #   taskA
        #   taskB
        #   taskC
        # @endmacro

        # @task on:local
        taskA() { echo "a"; }

        # @task on:local
        taskB() { echo "b"; }

        # @task on:local
        taskC() { echo "c"; }
        """,
    )

    result = parser.parse(path)

    assert len(result.macros) == 2
    assert result.macros["quick"].tasks == ["taskA", "taskB"]
    assert result.macros["full"].tasks == ["taskA", "taskB", "taskC"]


def test_parses_task_with_on_server(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    task = result.get_task("pull")
    assert task is not None
    assert task.name == "pull"
    assert task.servers == ["local"]
    assert task.parallel is False
    assert task.confirm is None
    assert "git pull origin $BRANCH" in task.script


def test_parses_task_with_parallel_flag(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    task = result.get_task("deployStagingParallel")
    assert task is not None
    assert task.parallel is True
    assert task.servers == ["staging"]


def test_parses_task_confirm_message(parser, tmp_path):
    path = _write(
        tmp_path,
        "confirm.sh",
        """\
        # @servers remote=forge@1.1.1.1

        # @task on:remote confirm="Are you sure you want to seed?"
        seed() {
            php artisan db:seed --force
        }
        """,
    )

    result = parser.parse(path)
    task = result.get_task("seed")

    assert task is not None
    assert task.confirm == "Are you sure you want to seed?"
    assert task.servers == ["remote"]


def test_parses_task_with_multiple_servers(parser, tmp_path):
    path = _write(
        tmp_path,
        "multi.sh",
        """\
        # @servers web-1=10.0.0.1 web-2=10.0.0.2

        # @task on:web-1,web-2
        restart() {
            sudo systemctl restart nginx
        }
        """,
    )

    result = parser.parse(path)
    task = result.get_task("restart")

    assert task is not None
    assert task.servers == ["web-1", "web-2"]


def test_parses_lifecycle_hooks_from_fixture(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    assert len(result.hooks) == 3

    before = result.get_hooks(HookType.BEFORE)
    after = result.get_hooks(HookType.AFTER)
    errors = result.get_hooks(HookType.ERROR)

    assert len(before) == 1
    assert len(after) == 1
    assert len(errors) == 1

    assert "Starting deployment" in before[0].script
    assert "Deployment complete" in after[0].script
    assert "Something went wrong" in errors[0].script


def test_parses_all_lifecycle_hook_types(parser, tmp_path):
    path = _write(
        tmp_path,
        "all_hooks.sh",
        """\
        # @servers local=127.0.0.1

        # @task on:local
        deploy() {
            echo "deploying"
        }

        # @before
        setup() {
            echo "before"
        }

        # @after
        teardown() {
            echo "after"
        }

        # @success
        onSuccess() {
            echo "success"
        }

        # @error
        onError() {
            echo "error"
        }

        # @finished
        onFinished() {
            echo "finished"
        }
        """,
    )

    result = parser.parse(path)

    assert len(result.hooks) == 5
    assert len(result.get_hooks(HookType.BEFORE)) == 1
    assert len(result.get_hooks(HookType.AFTER)) == 1
    assert len(result.get_hooks(HookType.SUCCESS)) == 1
    assert len(result.get_hooks(HookType.ERROR)) == 1
    assert len(result.get_hooks(HookType.FINISHED)) == 1


def test_parses_top_level_variable_assignments(parser, fixtures_path):
    result = parser.parse(str(fixtures_path / "complete.sh"))

    assert 'BRANCH="main"' in result.variable_preamble
    assert 'APP_DIR="/home/forge/myapp"' in result.variable_preamble


def test_extracts_helper_functions_into_preamble(parser, tmp_path):
    path = _write(
        tmp_path,
        "helper.sh",
        """\
        # @servers local=127.0.0.1

        format_date() {
            date +"%Y-%m-%d"
        }

        # @task on:local
        deploy() {
            echo "deploying at $(format_date)"
        }
        """,
    )

    result = parser.parse(path)

    assert "format_date()" in result.variable_preamble
    assert 'date +"%Y-%m-%d"' in result.variable_preamble


def test_handles_nested_braces_in_function_bodies(parser, tmp_path):
    path = _write(
        tmp_path,
        "nested.sh",
        """\
        # @servers local=127.0.0.1

        # @task on:local
        nested() {
            if [ "$ENV" = "production" ]; then
                if [ -d "/var/www" ]; then
                    echo "exists"
                fi
            fi
        }
        """,
    )

    result = parser.parse(path)
    task = result.get_task("nested")

    assert task is not None
    assert 'if [ "$ENV" = "production" ]' in task.script
    assert 'echo "exists"' in task.script


def test_adds_cli_data_to_variable_preamble(parser, tmp_path):
    path = _write(
        tmp_path,
        "simple.sh",
        """\
        # @servers local=127.0.0.1

        # @task on:local
        deploy() {
            echo "deploying $BRANCH"
        }
        """,
    )

    result = parser.parse(path, {"branch": "main", "env": "production"})

    assert "BRANCH='main'" in result.variable_preamble
    assert "ENV='production'" in result.variable_preamble


def test_parses_emoji_annotation(parser, tmp_path):
    path = _write(
        tmp_path,
        "emoji.sh",
        """\
        # @servers local=127.0.0.1

        # @task on:local emoji:🚀
        deploy() {
            echo "deploying"
        }

        # @task on:local
        noEmoji() {
            echo "no emoji"
        }
        """,
    )

    result = parser.parse(path)

    assert result.get_task("deploy").emoji == "🚀"
    assert result.get_task("noEmoji").emoji is None


def test_long_comment_above_task_does_not_misclassify_it_as_helper(parser, tmp_path):
    path = _write(
        tmp_path,
        "long_comment.sh",
        """\
        # @servers local=127.0.0.1

        # This is a deliberately very long comment block that pushes the @task
        # annotation more than 200 characters away from the function definition,
        # which used to trip up the helper-function detection heuristic that
        # looked back a fixed number of characters to find annotations. With the
        # name-based detection, this comment does not affect classification.
        # @task on:local
        deploy() {
            echo "deploying"
        }
        """,
    )

    result = parser.parse(path)

    assert result.get_task("deploy") is not None
    assert "deploy()" not in result.variable_preamble


def test_empty_file_produces_empty_result(parser, tmp_path):
    path = tmp_path / "empty.sh"
    path.write_text("")

    result = parser.parse(str(path))

    assert result.servers == {}
    assert result.tasks == {}
    assert result.macros == {}
    assert result.hooks == []
    assert result.variable_preamble == ""
