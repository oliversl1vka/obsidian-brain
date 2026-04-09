import logging
from dataclasses import dataclass
from src.scrapers.base import get_scraper_for_url
from src.llm.summarizer import Summarizer
from src.llm.categorizer import Categorizer
from src.llm.evaluator import Evaluator
from src.storage.writer import write_link_entry, check_duplicate, is_github_repository_url

logger = logging.getLogger(__name__)

class PipelineStepError(Exception):
    """Exception raised when a pipeline step fails."""
    pass

@dataclass
class PipelineResult:
    url: str
    title: str
    category: str
    summary: str
    status: str
    notify: bool

async def process_link(url: str) -> PipelineResult:
    """Core deterministic pipeline: Ingest -> Scrape -> Summarize -> Categorize -> Evaluate -> Store."""
    logger.info(f"Starting pipeline for: {url}")
    
    title = "Unknown"
    category = "Uncategorized"
    summary = "scrape_failed"
    status = "failed"
    notify = False
    
    try:
        # T019: Duplicate Check
        if not is_github_repository_url(url) and check_duplicate(url):
            logger.info(f"Duplicate link skipped: {url}")
            return PipelineResult(url, title, category, "Duplicate link, skipped.", "duplicate", False)
        
        # 1. Scrape (T031, T032)
        scraper = get_scraper_for_url(url)
        scrape_result = await scraper.scrape(url)
        title = scrape_result.title
        
        if scrape_result.status == "failed":
            summary = f"Scrape failed: {scrape_result.error_reason}"
            write_link_entry("Uncategorized", url, title, summary, scrape_result.status)
            return PipelineResult(url, title, "Uncategorized", summary, scrape_result.status, False)

        # 2. Summarize
        summarizer = Summarizer()
        summary = await summarizer.summarize(scrape_result.content)
        
        # 3. Categorize
        categorizer = Categorizer()
        category = await categorizer.categorize(summary)
        
        # 4. Evaluate
        evaluator = Evaluator()
        notify = await evaluator.evaluate(summary)

        # 5. Store
        status = "success"
        if notify:
            write_link_entry(category, url, title, summary, status)
        else:
            write_link_entry("bin", url, title, summary, status)
            category = "bin"

        return PipelineResult(url, title, category, summary, status, notify)
        
    except Exception as e:
        logger.exception(f"Unexpected error processing {url}: {e}")
        err_str = str(e).lower()
        if "rate" in err_str or "429" in err_str or "quota" in err_str:
            error_msg = f"rate_limit_error: {str(e)}"
        elif any(k in err_str for k in ("scrape", "http", "connect", "timeout", "ssl")):
            error_msg = f"scrape_error: {str(e)}"
        elif any(k in err_str for k in ("openai", "llm", "model", "token", "api")):
            error_msg = f"llm_error: {str(e)}"
        else:
            error_msg = f"pipeline_error: {str(e)}"
        try:
            write_link_entry("Uncategorized", url, title, error_msg, "failed")
        except Exception as storage_err:
            logger.error(f"Failed to store error entry for {url}: {storage_err}")
        return PipelineResult(url, title, "Uncategorized", error_msg, "failed", False)
