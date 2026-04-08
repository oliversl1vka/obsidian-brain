import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.config import settings
from src.pipeline import process_link, PipelineResult
from src.storage.writer import check_duplicate

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Hard cap on articles pulled per feed per digest run, to avoid runaway pipelines
# when a freshly added feed has hundreds of historical entries.
MAX_ARTICLES_PER_FEED = 5

# Common feed paths to probe when given a blog homepage
_FEED_GUESS_PATHS = [
    "/feed",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/index.xml",
    "/atom.xml",
    "/blog/feed",
    "/blog/rss.xml",
]

_AUTODISCOVER_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _read_sources() -> list[str]:
    """Read URLs from digest_sources_file. Skips blank lines and # comments."""
    sources_path = _PROJECT_ROOT / settings.digest_sources_file
    if not sources_path.exists():
        logger.info(f"Digest sources file not found: {sources_path}")
        return []
    urls = []
    for line in sources_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def _parse_feed(url: str) -> list[str]:
    """Parse a feed URL with feedparser. Returns up to MAX_ARTICLES_PER_FEED article links."""
    try:
        import feedparser
        parsed = feedparser.parse(url)
        if not parsed.entries:
            return []
        links = []
        for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
            link = getattr(entry, "link", None)
            if link:
                links.append(link)
        return links
    except Exception as e:
        logger.warning(f"feedparser failed on {url}: {e}")
        return []


async def _autodiscover_feed(url: str) -> str | None:
    """Fetch HTML and look for <link rel='alternate' type='application/rss+xml' href='...'>"""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 LinkStash/1.0"})
            if resp.status_code != 200:
                return None
            html = resp.text[:200_000]  # only inspect head-ish region
        match = _AUTODISCOVER_RE.search(html)
        if not match:
            return None
        feed_url = match.group(1)
        # Resolve relative URLs
        if feed_url.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            feed_url = f"{parsed.scheme}://{parsed.netloc}{feed_url}"
        elif not feed_url.startswith("http"):
            return None
        return feed_url
    except Exception as e:
        logger.warning(f"autodiscover failed on {url}: {e}")
        return None


async def _expand_to_article_urls(url: str) -> list[str]:
    """Expand a source URL into individual article URLs.

    Strategy:
      1. Try feedparser directly on the URL (works for explicit feed URLs).
      2. Try common feed paths (/feed, /rss.xml, etc.) on the same host.
      3. Try HTML autodiscovery (<link rel="alternate" type="application/rss+xml">).
      4. Fall back to [url] — caller scrapes the page itself (existing behavior).
    """
    # 1. Direct feed parse
    direct = _parse_feed(url)
    if direct:
        logger.info(f"Feed: {url} → {len(direct)} entries (direct)")
        return direct

    # 2. Probe common feed paths — both at host root AND under the URL's own path
    # (e.g. https://research.google/blog/ → https://research.google/blog/rss/)
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host_root = f"{parsed.scheme}://{parsed.netloc}"
    url_path = url.rstrip("/")
    candidates: list[str] = []
    for path in _FEED_GUESS_PATHS:
        candidates.append(url_path + path)
        candidates.append(url_path + path + "/")
        candidates.append(host_root + path)
    seen_guess: set[str] = set()
    for guess_url in candidates:
        if guess_url in seen_guess:
            continue
        seen_guess.add(guess_url)
        articles = _parse_feed(guess_url)
        if articles:
            logger.info(f"Feed: {url} → {guess_url} → {len(articles)} entries (guess)")
            return articles

    # 3. HTML autodiscovery
    discovered = await _autodiscover_feed(url)
    if discovered:
        articles = _parse_feed(discovered)
        if articles:
            logger.info(f"Feed: {url} → {discovered} → {len(articles)} entries (autodiscover)")
            return articles

    # 4. Fallback
    logger.info(f"No feed found for {url} — scraping page directly")
    return [url]


async def run_digest() -> list[PipelineResult]:
    """Read digest_sources.txt, expand any feeds, and process each URL through the pipeline."""
    sources = _read_sources()
    if not sources:
        logger.info("No URLs in digest sources file.")
        return []

    # Expand each source into one or more article URLs (feed-aware)
    all_urls: list[str] = []
    seen: set[str] = set()
    for src in sources:
        expanded = await _expand_to_article_urls(src)
        for u in expanded:
            if u not in seen:
                seen.add(u)
                all_urls.append(u)

    # Pre-filter already-processed URLs so we don't pay for scrape+LLM on dupes.
    # process_link does this internally too, but checking here saves the per-URL
    # function-call overhead and gives clearer log/digest counts.
    fresh_urls = [u for u in all_urls if not check_duplicate(u)]
    skipped_dupes = len(all_urls) - len(fresh_urls)
    logger.info(
        f"Running digest: {len(sources)} sources → {len(all_urls)} URLs "
        f"({skipped_dupes} already processed, {len(fresh_urls)} new)"
    )

    results: list[PipelineResult] = []
    for i, url in enumerate(fresh_urls):
        if i > 0:
            await asyncio.sleep(2.0)
        try:
            result = await process_link(url)
            results.append(result)
            logger.info(f"Digest [{result.status}]: {url}")
        except Exception as e:
            logger.error(f"Digest error for {url}: {e}")

    _write_digest_log(results)
    return results


def _write_digest_log(results: list[PipelineResult]) -> None:
    """Write a per-run log to obsidian-brain/Logs/."""
    logs_dir = settings.brain_dir / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = logs_dir / f"{date_str}-digest.md"

    success = [r for r in results if r.status == "success"]
    notify = [r for r in success if r.notify]
    binned = [r for r in success if not r.notify]
    skipped = [r for r in results if r.status == "duplicate"]
    failed = [r for r in results if r.status == "failed"]

    lines = [
        f"# Digest Run — {date_str}",
        "",
        f"**Total:** {len(results)} · **Saved:** {len(notify)} · **Binned:** {len(binned)} · **Duplicates:** {len(skipped)} · **Failed:** {len(failed)}",
        "",
    ]
    if notify:
        lines.append("## Saved to Brain")
        for r in notify:
            lines.append(f"- [{r.title}]({r.url}) — {r.category}")
        lines.append("")
    if failed:
        lines.append("## Failed")
        for r in failed:
            lines.append(f"- {r.url}: {r.summary}")
        lines.append("")

    log_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Digest log written: {log_path}")
