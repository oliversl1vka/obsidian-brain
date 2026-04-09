import pytest
from pathlib import Path
import shutil

from src.config import settings
from src.storage.writer import (
    GITHUB_REPO_STATE_FILE_NAME,
    check_duplicate,
    ensure_data_dir,
    get_last_checked_github_commit,
    is_github_repository_url,
    record_github_repo_check,
    write_link_entry,
)

test_data_dir = Path("tests/test_data")

@pytest.fixture(autouse=True)
def setup_teardown():
    original_data_dir = settings.data_dir
    settings.data_dir = test_data_dir
    # Setup
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Teardown
    settings.data_dir = original_data_dir
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)

def test_write_link_entry_creates_file():
    write_link_entry(
        category="Test Category",
        url="http://example.com",
        title="Test Title",
        summary="Test summary.",
        status="success"
    )
    
    expected_file = test_data_dir / "test-category.md"
    assert expected_file.exists()
    
    content = expected_file.read_text(encoding="utf-8")
    assert "# Test Category" in content
    assert "### Test Title" in content
    assert "**URL**: http://example.com" in content

def test_check_duplicate_finds_existing():
    write_link_entry(
        category="Test Category",
        url="http://unique-url.com",
        title="Test",
        summary="Test",
        status="success"
    )
    
    assert check_duplicate("http://unique-url.com") is True
    assert check_duplicate("http://not-found.com") is False


def test_prepend_ordering_newest_first():
    """Header stays at top, newest entry appears before older entry."""
    write_link_entry("Test Category", "http://first.com", "First", "First summary", "success")
    write_link_entry("Test Category", "http://second.com", "Second", "Second summary", "success")
    
    content = (test_data_dir / "test-category.md").read_text(encoding="utf-8")
    
    # Header must be at the very top
    assert content.startswith("# Test Category\n")
    
    # Second entry should appear before first entry (newest first)
    second_pos = content.index("http://second.com")
    first_pos = content.index("http://first.com")
    assert second_pos < first_pos


def test_index_md_created_and_updated():
    """FR-011: index.md is maintained as a master list."""
    write_link_entry("Cat A", "http://a.com", "Title A", "Summary A", "success")
    write_link_entry("Cat B", "http://b.com", "Title B", "Summary B", "success")
    
    index_path = test_data_dir / "index.md"
    assert index_path.exists()
    
    content = index_path.read_text(encoding="utf-8")
    assert "# LinkStash Index" in content
    assert "http://a.com" in content
    assert "http://b.com" in content
    # Newest first in index too
    b_pos = content.index("http://b.com")
    a_pos = content.index("http://a.com")
    assert b_pos < a_pos


def test_category_name_sanitization():
    """Category names with special chars become clean filenames."""
    write_link_entry("AI Tools & Open Source", "http://x.com", "T", "S", "success")
    expected_file = test_data_dir / "ai-tools-open-source.md"
    assert expected_file.exists()


def test_ensure_data_dir_creates_directory():
    """ensure_data_dir creates the data directory if missing."""
    import shutil as sh
    if test_data_dir.exists():
        sh.rmtree(test_data_dir)
    
    assert not test_data_dir.exists()
    ensure_data_dir()
    assert test_data_dir.exists()


def test_check_duplicate_no_data_dir():
    """check_duplicate returns False when data dir doesn't exist."""
    import shutil as sh
    if test_data_dir.exists():
        sh.rmtree(test_data_dir)
    
    assert check_duplicate("http://anything.com") is False


def test_github_repo_state_round_trip():
    record_github_repo_check("https://github.com/Owner/Repo/tree/main/src", "abc123")

    state_file = test_data_dir / GITHUB_REPO_STATE_FILE_NAME
    assert state_file.exists()
    assert get_last_checked_github_commit("https://github.com/owner/repo") == "abc123"
    assert get_last_checked_github_commit("https://github.com/owner/repo/issues") == "abc123"


def test_github_repo_state_file_is_not_treated_as_duplicate():
    record_github_repo_check("https://github.com/owner/repo", "abc123")

    assert check_duplicate("https://github.com/owner/repo") is False


def test_is_github_repository_url_ignores_notebooks():
    assert is_github_repository_url("https://github.com/owner/repo") is True
    assert is_github_repository_url("https://github.com/owner/repo/tree/main/src") is True
    assert is_github_repository_url("https://github.com/owner/repo/blob/main/notebook.ipynb") is False
