import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from src.config import settings

INDEX_FILE_NAME = "index.md"
GITHUB_REPO_STATE_FILE_NAME = "github-repo-state.md"
_EXCLUDED_METADATA_FILES = {INDEX_FILE_NAME, GITHUB_REPO_STATE_FILE_NAME}

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


def canonicalize_github_repo_url(url: str) -> str | None:
    """Return a normalized https://github.com/<owner>/<repo> URL, or None for non-repository GitHub URLs."""
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None

    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(path_parts) < 2:
        return None

    owner, repo = path_parts[0].lower(), path_parts[1].lower()
    if len(path_parts) == 2:
        return normalize_url(f"https://github.com/{owner}/{repo}")

    if path_parts[2].lower() != "tree":
        return None

    final_path_part = path_parts[-1].lower()
    if final_path_part.endswith(".ipynb"):
        return None

    return normalize_url(f"https://github.com/{owner}/{repo}")


def is_github_repository_url(url: str) -> bool:
    """Return False for non-repository GitHub URLs and True only for repository-like GitHub URLs."""
    return canonicalize_github_repo_url(url) is not None


def _github_repo_state_path() -> Path:
    return settings.data_dir / GITHUB_REPO_STATE_FILE_NAME


def get_last_checked_github_commit(url: str) -> str | None:
    """Return the recorded commit SHA, or None for invalid GitHub repo URLs or unknown repos."""
    canonical_url = canonicalize_github_repo_url(url)
    state_path = _github_repo_state_path()
    if not canonical_url or not state_path.exists():
        return None

    url_pattern = re.compile(r"- \*\*Repo URL\*\*: (.+)")
    commit_pattern = re.compile(r"- \*\*Last Checked Commit\*\*: (.+)")

    current_url: str | None = None
    with open(state_path, "r", encoding="utf-8") as state_file:
        for line in state_file:
            stripped_line = line.strip()
            url_match = url_pattern.match(stripped_line)
            if url_match:
                current_url = normalize_url(url_match.group(1).strip())
                continue

            commit_match = commit_pattern.match(stripped_line)
            if commit_match and current_url == canonical_url:
                return commit_match.group(1).strip()

    return None


def record_github_repo_check(url: str, commit_sha: str) -> None:
    """Persist the latest checked commit, returning early for invalid GitHub URLs or empty SHAs."""
    canonical_url = canonicalize_github_repo_url(url)
    if not canonical_url or not commit_sha:
        return

    ensure_data_dir()
    state_path = _github_repo_state_path()
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"## {canonical_url} ({checked_at})\n"
        f"- **Repo URL**: {canonical_url}\n"
        f"- **Last Checked Commit**: {commit_sha}\n"
        f"- **Checked At**: {checked_at}\n\n---\n\n"
    )

    header = "# GitHub Repo State\n\n"
    existing_entries = ""
    if state_path.exists():
        content = state_path.read_text(encoding="utf-8")
        if content.startswith(header):
            existing_entries = content[len(header):]
        else:
            existing_entries = content

    state_path.write_text(header + entry + existing_entries, encoding="utf-8")


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
        if md_file.name in _EXCLUDED_METADATA_FILES:
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
    index_path = settings.data_dir / INDEX_FILE_NAME
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
        if md_file.name in _EXCLUDED_METADATA_FILES:
            continue
        with open(md_file, "r", encoding="utf-8") as f:
            for line in f:
                match = url_pattern.match(line.strip())
                if match and normalize_url(match.group(1).strip()) == normalized:
                    return True
    return False
