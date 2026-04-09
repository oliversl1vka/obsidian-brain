import base64

import httpx
import pytest
from src.scrapers.base import ScrapeResult, BaseScraper, get_scraper_for_url, UnsupportedFormatScraper
from src.scrapers.github import GitHubScraper, MAX_STRUCTURE_ENTRIES
from src.scrapers.notebook import NotebookScraper
from src.scrapers.article import ArticleScraper
from src.scrapers.pdf import PdfScraper


# --- BaseScraper Tests ---

@pytest.mark.asyncio
async def test_base_scraper_failed_result():
    class DummyScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return self._create_failed_result(url, "test_failure")
            
    scraper = DummyScraper()
    result = await scraper.scrape("http://example.com")
    
    assert result.status == "failed"
    assert result.error_reason == "test_failure"
    assert result.url == "http://example.com"


# --- Scraper Factory Tests ---

def test_factory_returns_article_for_normal_url():
    scraper = get_scraper_for_url("https://example.com/article/123")
    assert isinstance(scraper, ArticleScraper)

def test_factory_returns_github_for_repo_url():
    scraper = get_scraper_for_url("https://github.com/owner/repo")
    assert isinstance(scraper, GitHubScraper)

def test_factory_returns_github_for_deep_repo_url():
    scraper = get_scraper_for_url("https://github.com/owner/repo/tree/main/src")
    assert isinstance(scraper, GitHubScraper)

def test_factory_returns_notebook_for_ipynb():
    scraper = get_scraper_for_url("https://github.com/owner/repo/blob/main/notebook.ipynb")
    assert isinstance(scraper, NotebookScraper)

def test_factory_returns_notebook_for_non_github_ipynb():
    scraper = get_scraper_for_url("https://example.com/data/analysis.ipynb")
    assert isinstance(scraper, NotebookScraper)

def test_factory_returns_pdf_scraper_for_pdf():
    scraper = get_scraper_for_url("https://example.com/paper.pdf")
    assert isinstance(scraper, PdfScraper)

def test_factory_returns_unsupported_for_zip():
    scraper = get_scraper_for_url("https://example.com/archive.zip")
    assert isinstance(scraper, UnsupportedFormatScraper)


# --- GitHubScraper Tests ---

@pytest.mark.asyncio
async def test_github_scraper_invalid_url():
    scraper = GitHubScraper()
    result = await scraper.scrape("https://github.com/invalid") # Missing repo
    assert result.status == "failed"
    assert "Invalid GitHub repository" in result.error_reason


class FakeResponse:
    def __init__(self, url: str, status_code: int, payload: dict):
        self.url = url
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", self.url)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=request, response=response)


class FakeAsyncClient:
    def __init__(self, responses: dict[str, FakeResponse], calls: list[str], **kwargs):
        self.responses = responses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        self.calls.append(url)
        return self.responses[url]


def _inject_base64_line_break(content: str, position: int = 4) -> str:
    return content[:position] + "\n" + content[position:]


@pytest.mark.asyncio
async def test_github_scraper_first_scrape_collects_full_repository(monkeypatch):
    scraper = GitHubScraper()
    calls = []
    recorded_commits = []
    responses = {
        "https://api.github.com/repos/owner/repo": FakeResponse(
            "https://api.github.com/repos/owner/repo",
            200,
            {"description": "Repo description", "default_branch": "main", "language": "Python"},
        ),
        "https://api.github.com/repos/owner/repo/branches/main": FakeResponse(
            "https://api.github.com/repos/owner/repo/branches/main",
            200,
            {"commit": {"sha": "head123"}},
        ),
        "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1": FakeResponse(
            "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1",
            200,
            {
                "tree": [
                    {"path": "README.md", "type": "blob", "sha": "sha-readme", "size": 9},
                    {"path": "src", "type": "tree"},
                    {"path": "src/app.py", "type": "blob", "sha": "sha-app", "size": 12},
                    {"path": ".gitignore", "type": "blob", "sha": "sha-ignore", "size": 6},
                    {"path": "image.png", "type": "blob", "sha": "sha-image", "size": 12},
                ]
            },
        ),
        "https://api.github.com/repos/owner/repo/git/blobs/sha-readme": FakeResponse(
            "https://api.github.com/repos/owner/repo/git/blobs/sha-readme",
            200,
            {
                "encoding": "base64",
                "content": _inject_base64_line_break(base64.b64encode(b"# Hello\n").decode("utf-8")),
            },
        ),
        "https://api.github.com/repos/owner/repo/git/blobs/sha-app": FakeResponse(
            "https://api.github.com/repos/owner/repo/git/blobs/sha-app",
            200,
            {"encoding": "base64", "content": base64.b64encode(b'print("hi")\n').decode("utf-8")},
        ),
        "https://api.github.com/repos/owner/repo/git/blobs/sha-ignore": FakeResponse(
            "https://api.github.com/repos/owner/repo/git/blobs/sha-ignore",
            200,
            {"encoding": "base64", "content": base64.b64encode(b".venv\n").decode("utf-8")},
        ),
    }

    monkeypatch.setattr("src.scrapers.github.get_last_checked_github_commit", lambda url: None)
    monkeypatch.setattr("src.scrapers.github.record_github_repo_check", lambda url, sha: recorded_commits.append((url, sha)))
    monkeypatch.setattr(
        "src.scrapers.github.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, calls, **kwargs),
    )

    result = await scraper.scrape("https://github.com/owner/repo")

    assert result.status == "success"
    assert "Previously checked commit: None" in result.content
    assert "--- FILE CONTENTS ---" in result.content
    assert "### README.md" in result.content
    assert "### .gitignore" in result.content
    assert 'print("hi")' in result.content
    assert "image.png" in result.content
    assert all("/compare/" not in call for call in calls)
    assert recorded_commits == [("https://github.com/owner/repo", "head123")]


@pytest.mark.asyncio
async def test_github_scraper_limits_structure_output(monkeypatch):
    scraper = GitHubScraper()
    calls = []
    recorded_commits = []
    large_tree_size = MAX_STRUCTURE_ENTRIES + 5
    large_tree = [
        {"path": f"file-{file_index}.py", "type": "blob", "sha": f"sha-{file_index}", "size": 999999}
        for file_index in range(large_tree_size)
    ]
    responses = {
        "https://api.github.com/repos/owner/repo": FakeResponse(
            "https://api.github.com/repos/owner/repo",
            200,
            {"description": "Repo description", "default_branch": "main", "language": "Python"},
        ),
        "https://api.github.com/repos/owner/repo/branches/main": FakeResponse(
            "https://api.github.com/repos/owner/repo/branches/main",
            200,
            {"commit": {"sha": "head123"}},
        ),
        "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1": FakeResponse(
            "https://api.github.com/repos/owner/repo/git/trees/main?recursive=1",
            200,
            {"tree": large_tree},
        ),
    }

    monkeypatch.setattr("src.scrapers.github.get_last_checked_github_commit", lambda url: None)
    monkeypatch.setattr("src.scrapers.github.record_github_repo_check", lambda url, sha: recorded_commits.append((url, sha)))
    monkeypatch.setattr(
        "src.scrapers.github.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, calls, **kwargs),
    )

    result = await scraper.scrape("https://github.com/owner/repo")

    assert result.status == "success"
    assert f"file-{MAX_STRUCTURE_ENTRIES - 1}.py" in result.content
    assert f"file-{large_tree_size - 1}.py" not in result.content
    assert "Truncated 5 additional paths" in result.content
    assert recorded_commits == [("https://github.com/owner/repo", "head123")]


@pytest.mark.asyncio
async def test_github_scraper_repeat_scrape_uses_compare_api(monkeypatch):
    scraper = GitHubScraper()
    calls = []
    recorded_commits = []
    responses = {
        "https://api.github.com/repos/owner/repo": FakeResponse(
            "https://api.github.com/repos/owner/repo",
            200,
            {"description": "Repo description", "default_branch": "main", "language": "Python"},
        ),
        "https://api.github.com/repos/owner/repo/branches/main": FakeResponse(
            "https://api.github.com/repos/owner/repo/branches/main",
            200,
            {"commit": {"sha": "head456"}},
        ),
        "https://api.github.com/repos/owner/repo/compare/old123...head456": FakeResponse(
            "https://api.github.com/repos/owner/repo/compare/old123...head456",
            200,
            {
                "commits": [{"sha": "head456", "commit": {"message": "Add feature"}}],
                "files": [
                    {
                        "filename": "src/app.py",
                        "status": "modified",
                        "additions": 2,
                        "deletions": 1,
                        "patch": "@@ -1 +1 @@\n-print('old')\n+print('new')",
                    }
                ],
            },
        ),
    }

    monkeypatch.setattr("src.scrapers.github.get_last_checked_github_commit", lambda url: "old123")
    monkeypatch.setattr("src.scrapers.github.record_github_repo_check", lambda url, sha: recorded_commits.append((url, sha)))
    monkeypatch.setattr(
        "src.scrapers.github.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(responses, calls, **kwargs),
    )

    result = await scraper.scrape("https://github.com/owner/repo")

    assert result.status == "success"
    assert "Previously checked commit: old123" in result.content
    assert "--- CHANGES SINCE LAST CHECK ---" in result.content
    assert "From old123 to head456" in result.content
    assert "### src/app.py" in result.content
    assert "--- FILE CONTENTS ---" not in result.content
    assert any("/compare/old123...head456" in call for call in calls)
    assert recorded_commits == [("https://github.com/owner/repo", "head456")]


# --- NotebookScraper Tests ---

@pytest.mark.asyncio
async def test_notebook_scraper_invalid_json():
    scraper = NotebookScraper()
    result = await scraper.scrape("https://example.com")
    assert result.status == "failed"


# --- ArticleScraper Tests ---

@pytest.mark.asyncio
async def test_article_scraper_invalid_url():
    scraper = ArticleScraper()
    result = await scraper.scrape("https://this-domain-does-not-exist-xyz123.com")
    assert result.status == "failed"
    assert result.error_reason  # Should have a reason

@pytest.mark.asyncio
async def test_unsupported_format_scraper():
    scraper = UnsupportedFormatScraper()
    result = await scraper.scrape("https://example.com/file.pdf")
    assert result.status == "failed"
    assert "Unsupported" in result.error_reason
