import pytest
import shutil
from pathlib import Path
from src.pipeline import process_link
from src.config import settings
from src.scrapers.base import ScrapeResult

# Use isolated test data dir for integration tests
test_data_dir = Path("tests/test_data_integration")


@pytest.fixture(autouse=True)
def setup_teardown():
    original_data_dir = settings.data_dir
    settings.data_dir = test_data_dir
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)
    test_data_dir.mkdir(parents=True, exist_ok=True)
    yield
    settings.data_dir = original_data_dir
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)


# --- US1: Single Link Pipeline ---

@pytest.mark.asyncio
async def test_pipeline_duplicate_handling():
    """Duplicate URL returns early with status='duplicate'."""
    import src.pipeline
    original_check = src.pipeline.check_duplicate
    src.pipeline.check_duplicate = lambda url: True
    
    try:
        result = await process_link("http://example.com/duplicate")
        assert result.status == "duplicate"
        assert result.notify is False
    finally:
        src.pipeline.check_duplicate = original_check


@pytest.mark.asyncio
async def test_pipeline_github_repo_url_bypasses_duplicate_guard():
    """GitHub repository URLs should be reprocessed so the scraper can check for new commits."""
    import src.pipeline
    from src.scrapers.base import BaseScraper
    from src.llm.summarizer import Summarizer
    from src.llm.categorizer import Categorizer
    from src.llm.evaluator import Evaluator

    class MockGitHubScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="owner/repo", content="Repository diff", status="success")

    class MockSummarizer(Summarizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "Repository summary."

    class MockCategorizer(Categorizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "AI Tools & Open Source"

    class MockEvaluator(Evaluator):
        async def generate_response(self, p, c, max_tokens=500):
            return "notify"

    original_get_scraper = src.pipeline.get_scraper_for_url
    original_dup = src.pipeline.check_duplicate
    orig_summarizer = src.pipeline.Summarizer
    orig_categorizer = src.pipeline.Categorizer
    orig_evaluator = src.pipeline.Evaluator

    src.pipeline.get_scraper_for_url = lambda url: MockGitHubScraper()
    src.pipeline.check_duplicate = lambda url: True
    src.pipeline.Summarizer = MockSummarizer
    src.pipeline.Categorizer = MockCategorizer
    src.pipeline.Evaluator = MockEvaluator

    try:
        result = await process_link("https://github.com/owner/repo")

        assert result.status == "success"
        assert result.title == "owner/repo"
        assert result.notify is True
    finally:
        src.pipeline.get_scraper_for_url = original_get_scraper
        src.pipeline.check_duplicate = original_dup
        src.pipeline.Summarizer = orig_summarizer
        src.pipeline.Categorizer = orig_categorizer
        src.pipeline.Evaluator = orig_evaluator


@pytest.mark.asyncio
async def test_pipeline_single_link_happy_path():
    """US1: Full pipeline with mocked scraper and LLM produces a stored success result."""
    import src.pipeline
    from src.scrapers.base import BaseScraper
    from src.llm.summarizer import Summarizer
    from src.llm.categorizer import Categorizer
    from src.llm.evaluator import Evaluator
    
    # Mock scraper
    class MockScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="Test Article", content="Article about Python testing.", status="success")
    
    # Mock LLM modules
    class MockSummarizer(Summarizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "A concise summary about Python testing best practices."
    
    class MockCategorizer(Categorizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "AI Tools & Open Source"
    
    class MockEvaluator(Evaluator):
        async def generate_response(self, p, c, max_tokens=500):
            return "notify"
    
    # Patch pipeline components
    original_get_scraper = src.pipeline.get_scraper_for_url
    original_dup = src.pipeline.check_duplicate
    src.pipeline.get_scraper_for_url = lambda url: MockScraper()
    src.pipeline.check_duplicate = lambda url: False
    
    # Patch LLM class constructors
    orig_summarizer = src.pipeline.Summarizer
    orig_categorizer = src.pipeline.Categorizer
    orig_evaluator = src.pipeline.Evaluator
    src.pipeline.Summarizer = MockSummarizer
    src.pipeline.Categorizer = MockCategorizer
    src.pipeline.Evaluator = MockEvaluator
    
    try:
        result = await process_link("http://example.com/test-article")
        
        assert result.status == "success"
        assert result.title == "Test Article"
        assert result.category == "AI Tools & Open Source"
        assert result.notify is True
        assert "Python testing" in result.summary
        assert result.scrape_content == "Article about Python testing."
        
        # Verify file was written
        cat_file = test_data_dir / "ai-tools-open-source.md"
        assert cat_file.exists()
        content = cat_file.read_text(encoding="utf-8")
        assert "http://example.com/test-article" in content
        
        # Verify index.md was updated
        index_file = test_data_dir / "index.md"
        assert index_file.exists()
        assert "http://example.com/test-article" in index_file.read_text(encoding="utf-8")
    finally:
        src.pipeline.get_scraper_for_url = original_get_scraper
        src.pipeline.check_duplicate = original_dup
        src.pipeline.Summarizer = orig_summarizer
        src.pipeline.Categorizer = orig_categorizer
        src.pipeline.Evaluator = orig_evaluator


@pytest.mark.asyncio
async def test_pipeline_scrape_failure():
    """When scraper fails, result is stored under Uncategorized with failed status."""
    import src.pipeline
    from src.scrapers.base import BaseScraper
    
    class FailingScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="Unknown", content="", status="failed", error_reason="Connection refused")
    
    original_get_scraper = src.pipeline.get_scraper_for_url
    original_dup = src.pipeline.check_duplicate
    src.pipeline.get_scraper_for_url = lambda url: FailingScraper()
    src.pipeline.check_duplicate = lambda url: False
    
    try:
        result = await process_link("http://example.com/dead-link")
        assert result.status == "failed"
        assert result.category == "Uncategorized"
        assert "Scrape failed" in result.summary
    finally:
        src.pipeline.get_scraper_for_url = original_get_scraper
        src.pipeline.check_duplicate = original_dup


# --- US2: Batch Processing & Notification ---

@pytest.mark.asyncio
async def test_pipeline_batch_processing():
    """US2: Multiple URLs processed sequentially, each returns a PipelineResult."""
    import src.pipeline
    from src.scrapers.base import BaseScraper
    from src.llm.summarizer import Summarizer
    from src.llm.categorizer import Categorizer
    from src.llm.evaluator import Evaluator
    
    call_count = 0
    
    class MockScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title=f"Article {url[-1]}", content="Content", status="success")
    
    class MockSummarizer(Summarizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "A brief summary."
    
    class MockCategorizer(Categorizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "Uncategorized"
    
    class MockEvaluator(Evaluator):
        async def generate_response(self, p, c, max_tokens=500):
            nonlocal call_count
            call_count += 1
            # Only first URL is "relevant"
            return "notify" if call_count == 1 else "do not notify"
    
    original_get_scraper = src.pipeline.get_scraper_for_url
    original_dup = src.pipeline.check_duplicate
    orig_summarizer = src.pipeline.Summarizer
    orig_categorizer = src.pipeline.Categorizer
    orig_evaluator = src.pipeline.Evaluator
    
    src.pipeline.get_scraper_for_url = lambda url: MockScraper()
    src.pipeline.check_duplicate = lambda url: False
    src.pipeline.Summarizer = MockSummarizer
    src.pipeline.Categorizer = MockCategorizer
    src.pipeline.Evaluator = MockEvaluator
    
    try:
        urls = ["http://example.com/1", "http://example.com/2", "http://example.com/3"]
        results = []
        for url in urls:
            results.append(await process_link(url))
        
        assert len(results) == 3
        assert all(r.status == "success" for r in results)
        # Only first should trigger notification
        assert results[0].notify is True
        assert results[1].notify is False
        assert results[2].notify is False
    finally:
        src.pipeline.get_scraper_for_url = original_get_scraper
        src.pipeline.check_duplicate = original_dup
        src.pipeline.Summarizer = orig_summarizer
        src.pipeline.Categorizer = orig_categorizer
        src.pipeline.Evaluator = orig_evaluator


# --- US3: Multi-Type Scraping ---

@pytest.mark.asyncio
async def test_pipeline_multi_type_scraping():
    """US3: Different URL types route to appropriate scrapers and produce distinct results."""
    import src.pipeline
    from src.scrapers.base import BaseScraper
    from src.llm.summarizer import Summarizer
    from src.llm.categorizer import Categorizer
    from src.llm.evaluator import Evaluator
    
    class MockArticleScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="News Article", content="Article text", status="success")
    
    class MockGitHubScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="owner/repo", content="--- STRUCTURE ---\nREADME", status="success")
    
    class MockNotebookScraper(BaseScraper):
        async def scrape(self, url: str) -> ScrapeResult:
            return ScrapeResult(url=url, title="analysis.ipynb", content="[MARKDOWN]\n# Analysis", status="success")
    
    class MockSummarizer(Summarizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "Summary."
    
    class MockCategorizer(Categorizer):
        async def generate_response(self, p, c, max_tokens=500):
            return "AI Tools & Open Source"
    
    class MockEvaluator(Evaluator):
        async def generate_response(self, p, c, max_tokens=500):
            return "do not notify"
    
    scraper_sequence = iter([MockArticleScraper(), MockGitHubScraper(), MockNotebookScraper()])
    
    original_get_scraper = src.pipeline.get_scraper_for_url
    original_dup = src.pipeline.check_duplicate
    orig_summarizer = src.pipeline.Summarizer
    orig_categorizer = src.pipeline.Categorizer
    orig_evaluator = src.pipeline.Evaluator
    
    src.pipeline.get_scraper_for_url = lambda url: next(scraper_sequence)
    src.pipeline.check_duplicate = lambda url: False
    src.pipeline.Summarizer = MockSummarizer
    src.pipeline.Categorizer = MockCategorizer
    src.pipeline.Evaluator = MockEvaluator
    
    try:
        r1 = await process_link("http://example.com/article")
        r2 = await process_link("https://github.com/owner/repo")
        r3 = await process_link("https://example.com/notebook.ipynb")
        
        assert r1.title == "News Article"
        assert r2.title == "owner/repo"
        assert r3.title == "analysis.ipynb"
        assert all(r.status == "success" for r in [r1, r2, r3])
    finally:
        src.pipeline.get_scraper_for_url = original_get_scraper
        src.pipeline.check_duplicate = original_dup
        src.pipeline.Summarizer = orig_summarizer
        src.pipeline.Categorizer = orig_categorizer
        src.pipeline.Evaluator = orig_evaluator
