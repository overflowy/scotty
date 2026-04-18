from __future__ import annotations

from scotty.parsing.models import TaskDefinition


def test_camel_case_is_humanized():
    assert TaskDefinition(name="startDeployment", script="").display_name() == "Start deployment"


def test_multi_word_camel_case():
    assert TaskDefinition(name="cloneRepository", script="").display_name() == "Clone repository"


def test_single_word():
    assert TaskDefinition(name="deploy", script="").display_name() == "Deploy"


def test_snake_case():
    assert TaskDefinition(name="clear_cache", script="").display_name() == "Clear cache"


def test_kebab_case():
    assert TaskDefinition(name="deploy-code", script="").display_name() == "Deploy code"


def test_consecutive_uppercase_letters():
    assert TaskDefinition(name="deployOnlySSH", script="").display_name() == "Deploy only ssh"


def test_display_name_excludes_emoji():
    task = TaskDefinition(name="startDeployment", script="", emoji="🏃")
    assert task.display_name() == "Start deployment"


def test_display_name_with_emoji_prepends_emoji():
    task = TaskDefinition(name="startDeployment", script="", emoji="🏃")
    assert task.display_name_with_emoji() == "🏃  Start deployment"


def test_display_name_with_emoji_returns_plain_when_no_emoji():
    task = TaskDefinition(name="deploy", script="", emoji=None)
    assert task.display_name_with_emoji() == "Deploy"
