import os
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from src.config import settings

def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication: lowercase scheme/host, strip trailing slash, sort query params."""
    try:
        parsed = urlparse(url)
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=parsed.path.rstrip("/") or "/",
            query=urlencode(sorted(parse_qsl(parsed.query))),
            fragment="",
        )
        return urlunparse(normalized)
    except Exception:
        return url


def get_link_stats() -> dict:
    """Return total links saved, per-category counts, and the 3 most recent entries."""
    if not settings.data_dir.exists():
        return {"total": 0, "by_category": {}, "recent": []}

    by_category: dict[str, int] = {}
    recent: list[dict] = []

    url_pattern = re.compile(r"- \*\*URL\*\*: (.+)")
    title_pattern = re.compile(r"^### (.+?) \(\d{4}-\d{2}-\d{2}")
    date_pattern = re.compile(r"\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)")

    for md_file in sorted(settings.data_dir.glob("*.md"), key=lambda f: f.name):
        if md_file.name == "index.md":
            continue
        category = md_file.stem.replace("-", " ").title()
        count = 0
        lines = md_file.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            title_match = title_pattern.match(lines[i])
            if title_match:
                count += 1
                title = title_match.group(1)
                date_match = date_pattern.search(lines[i])
                date_str = date_match.group(1) if date_match else ""
                url = ""
                if i + 1 < len(lines):
                    url_match = url_pattern.match(lines[i + 1])
                    if url_match:
                        url = url_match.group(1)
                recent.append({"title": title, "url": url, "category": category, "date": date_str})
            i += 1
        if count:
            by_category[category] = count

    recent.sort(key=lambda x: x["date"], reverse=True)
    total = sum(by_category.values())
    return {"total": total, "by_category": by_category, "recent": recent[:3]}


def ensure_data_dir():
    settings.data_dir.mkdir(parents=True, exist_ok=True)

def _category_file(category: str) -> Path:
    """Returns the path to the category file as a flat .md file in the data dir."""
    file_name = category.lower().replace(" & ", "-").replace(" ", "-") + ".md"
    return settings.data_dir / file_name


def write_link_entry(category: str, url: str, title: str, summary: str, status: str):
    """Appends a link entry to the respective category file."""
    ensure_data_dir()

    file_path = _category_file(category)
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    entry = f"### {title} ({date_str})\n"
    entry += f"- **URL**: {url}\n"
    entry += f"- **Status**: {status}\n"
    entry += f"- **Summary**: {summary}\n\n---\n\n"
    
    # Prepend to file: always keep header at top, insert new entry after header.
    header = f"# {category}\n\n"
    existing_entries = ""
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip existing header so we can re-write it cleanly at the top
        if content.startswith(header):
            existing_entries = content[len(header):]
        else:
            existing_entries = content
            
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(entry)
        f.write(existing_entries)

    # FR-011: Maintain index.md as master list of all links
    _update_index(category, url, title, date_str)


def _update_index(category: str, url: str, title: str, date_str: str) -> None:
    """Prepend a new entry to data/index.md (newest first)."""
    index_path = settings.data_dir / "index.md"
    index_entry = f"- [{title}]({url}) — **{category}** ({date_str})\n"

    index_header = "# LinkStash Index\n\n"
    existing = ""
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.startswith(index_header):
            existing = content[len(index_header):]
        else:
            existing = content

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_header)
        f.write(index_entry)
        f.write(existing)


def check_duplicate(url: str) -> bool:
    """Checks if a URL already exists in any markdown file, using normalized URL comparison."""
    if not settings.data_dir.exists():
        return False

    normalized = normalize_url(url)
    url_pattern = re.compile(r"- \*\*URL\*\*: (.+)")

    for md_file in settings.data_dir.rglob("*.md"):
        with open(md_file, "r", encoding="utf-8") as f:
            for line in f:
                match = url_pattern.match(line.strip())
                if match and normalize_url(match.group(1).strip()) == normalized:
                    return True
    return False
