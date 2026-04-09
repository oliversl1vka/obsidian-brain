from pathlib import Path

import pytest
from git import Repo
from git.remote import Remote

from src.brain.formatter import FormattedEntry
from src.brain.git_bootstrap import bootstrap_brain_git
from src.brain.git_ops import BrainGitOps
from src.brain.git_utils import sanitize_git_error_message
from src.brain.skill_writer import SkillWriter
from src.brain.writer import BrainWriter
from src.config import load_config, settings
from src.llm.skill_formatter import ReferenceFile


@pytest.fixture
def brain_test_dir(tmp_path: Path):
    original_brain_dir = settings.brain_dir
    original_skills_dir = settings.skills_dir
    original_categories = settings.categories
    settings.brain_dir = tmp_path / "brain"
    settings.skills_dir = settings.brain_dir / "Claude-Code"
    settings.categories = ["AI Tools & Open Source", "Research & Papers"]
    yield settings.brain_dir
    settings.brain_dir = original_brain_dir
    settings.skills_dir = original_skills_dir
    settings.categories = original_categories


def test_load_config_defaults_brain_dir_under_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BRAIN_DIR", raising=False)
    monkeypatch.delenv("SKILLS_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "persisted-data"))

    config = load_config()

    assert config.brain_dir == Path(tmp_path / "persisted-data") / "obsidian-brain"
    assert config.skills_dir == config.brain_dir / "Claude-Code"


def test_sanitize_git_error_message_redacts_credentials():
    raw = (
        "fatal: unable to access "
        "'https://x-access-token:ghp_secret123@github.com/example/private.git/' "
        "and 'https://user:password123@example.com/repo.git'"
    )

    sanitized = sanitize_git_error_message(raw)

    assert "ghp_secret123" not in sanitized
    assert "password123" not in sanitized
    assert "x-access-token:***@" in sanitized
    assert "user:***@" in sanitized


def test_brain_writer_creates_home_page_for_new_vault(brain_test_dir: Path):
    writer = BrainWriter()

    written = writer.write_entry(
        FormattedEntry(
            title="Private brain repo",
            url="https://example.com/private-brain",
            date="2026-04-08",
            category="AI Tools & Open Source",
            context="Context",
            insight="Insight",
            application="Application",
        )
    )

    home_content = (brain_test_dir / "Home.md").read_text(encoding="utf-8")

    assert written.entry_path.exists()
    assert "[[Topics/AI Tools & Open Source]]" in home_content
    assert "Private brain repo" in home_content


def test_skill_writer_indexes_and_shortlists_relevant_entries(brain_test_dir: Path):
    writer = SkillWriter()

    writer.write_artifact(
        artifact_type="skill",
        name="browser-regression-testing",
        description="Run browser regression testing workflows and capture failures. Use when validating UI changes.",
        domain_path="development/testing",
        content=(
            "---\n"
            "name: browser-regression-testing\n"
            "description: Run browser regression testing workflows and capture failures. Use when validating UI changes.\n"
            "---\n\n"
            "# Browser Regression Testing\n\n"
            "## Workflow\n"
            "1. Run the browser suite.\n"
        ),
        source_url="https://github.com/example/browser-testing-kit",
        references=[ReferenceFile(filename="playwright-notes.md", content="# Playwright Notes\n")],
    )
    writer.write_artifact(
        artifact_type="prompt",
        name="release-prompt",
        description="Prompt template for release reviews. Use when preparing changelog-ready summaries.",
        domain_path="development/release",
        content=(
            "---\n"
            "name: release-prompt\n"
            "description: Prompt template for release reviews. Use when preparing changelog-ready summaries.\n"
            "type: prompt\n"
            "---\n\n"
            "# Release Prompt\n"
        ),
        source_url="https://example.com/release-guide",
    )

    manifest = writer.get_skill_manifest()
    relevant = writer.find_relevant_entries(
        "https://github.com/example/browser-testing-kit",
        "Browser testing toolkit",
        "A workflow for browser regression testing, debugging flaky UI tests, and capturing failures.",
    )

    assert (settings.skills_dir / "index.md").exists()
    assert any(entry.name == "browser-regression-testing" for entry in manifest)
    assert relevant
    assert relevant[0].name == "browser-regression-testing"
    assert (settings.skills_dir / "skills" / "development" / "testing" / "browser-regression-testing" / "references" / "playwright-notes.md").exists()


def test_brain_git_ops_uses_configured_brain_repo(brain_test_dir: Path):
    repo = Repo.init(brain_test_dir)
    with repo.config_writer() as config_writer:
        config_writer.set_value("user", "email", "test@example.com")
        config_writer.set_value("user", "name", "Test User")

    entries_dir = brain_test_dir / "Entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / "2026-04-08-entry.md").write_text("# Entry\n", encoding="utf-8")

    ops = BrainGitOps()

    assert ops.has_changes() is True

    result = ops.commit_brain("brain: add test entry")

    assert result.success is True
    assert ops.get_entry_count() == 1
    assert ops.has_changes() is False


def test_bootstrap_brain_git_initializes_local_repo_without_remote(
    brain_test_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GIT_REPO_SLUG", raising=False)
    monkeypatch.setenv("GIT_BRANCH", "master")

    assert bootstrap_brain_git() is True
    assert (brain_test_dir / ".git").exists()


def test_bootstrap_brain_git_configures_separate_private_remote(
    brain_test_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    monkeypatch.setenv("GIT_REPO_SLUG", "example/private-brain")
    monkeypatch.setenv("GIT_BRANCH", "master")
    monkeypatch.setattr(Remote, "fetch", lambda self: None)

    assert bootstrap_brain_git() is True

    repo = Repo(brain_test_dir)
    assert repo.remotes.origin.url == "https://x-access-token:ghp_testtoken@github.com/example/private-brain.git"
