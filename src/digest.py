import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings
from src.pipeline import process_link, PipelineResult

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


async def run_digest() -> list[PipelineResult]:
    """Read digest_sources.txt and process each URL through the LinkStash pipeline."""
    urls = _read_sources()
    if not urls:
        logger.info("No URLs in digest sources file.")
        return []

    logger.info(f"Running digest: {len(urls)} URLs")
    results: list[PipelineResult] = []
    for i, url in enumerate(urls):
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
