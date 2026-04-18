from __future__ import annotations

import pytest

from scotty.execution.task_result import TaskResult


def test_succeeded_when_exit_code_is_zero():
    assert TaskResult(exit_code=0).succeeded() is True


def test_not_succeeded_when_exit_code_is_one():
    assert TaskResult(exit_code=1).succeeded() is False


@pytest.mark.parametrize("code", [1, 2, 127, 255])
def test_not_succeeded_with_various_non_zero_codes(code):
    assert TaskResult(exit_code=code).succeeded() is False
