import logging
import os
from binascii import Error as BinasciiError
from base64 import b64decode
from typing import Any
from urllib.parse import urlparse

import httpx

from src.scrapers.base import BaseScraper, ScrapeResult
from src.storage.writer import get_last_checked_github_commit, record_github_repo_check

logger = logging.getLogger(__name__)

MAX_REPO_FILES = 60
MAX_BLOB_BYTES = 20_000
MAX_TOTAL_CONTENT_CHARS = 120_000
_BINARY_EXTENSIONS = {
    ".7z", ".bin", ".class", ".dll", ".dylib", ".exe", ".gif", ".gz", ".ico", ".jar", ".jpeg",
    ".jpg", ".lock", ".pdf", ".png", ".pyc", ".so", ".tar", ".woff", ".woff2", ".zip",
}
_TEXT_FILE_NAMES = {"dockerfile", "makefile", "readme", "license", "procfile"}


class GitHubScraper(BaseScraper):
    async def scrape(self, url: str) -> ScrapeResult:
        # url format: https://github.com/owner/repo
        try:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.strip("/").split("/") if part]
            if len(path_parts) < 2:
                return self._create_failed_result(url, "Invalid GitHub repository URL")

            owner, repo = path_parts[0], path_parts[1]
            api_base = f"https://api.github.com/repos/{owner}/{repo}"
            last_checked_commit = get_last_checked_github_commit(url)

            github_token = os.environ.get("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                repo_resp = await client.get(api_base)
                if repo_resp.status_code == 404:
                    return self._create_failed_result(url, "Repository not found or private")
                repo_resp.raise_for_status()
                repo_data = repo_resp.json()

                title = f"{owner}/{repo} - {repo_data.get('description', '')}"
                default_branch = repo_data.get("default_branch", "main")

                branch_resp = await client.get(f"{api_base}/branches/{default_branch}")
                branch_resp.raise_for_status()
                branch_data = branch_resp.json()
                head_commit = branch_data.get("commit", {}).get("sha", "")
                if not head_commit:
                    return self._create_failed_result(url, "Could not determine repository HEAD commit")

                repo_summary = self._build_repo_summary(
                    owner, repo, repo_data, default_branch, head_commit, last_checked_commit
                )
                if last_checked_commit and last_checked_commit != head_commit:
                    repo_content = await self._build_incremental_content(
                        client, api_base, last_checked_commit, head_commit
                    )
                    if repo_content is None:
                        full_snapshot = await self._build_full_content(client, api_base, default_branch)
                        repo_content = (
                            f"--- CHANGES SINCE LAST CHECK ---\n"
                            f"Could not diff {last_checked_commit}..{head_commit}; using a full snapshot instead.\n\n"
                            f"{full_snapshot}"
                        )
                elif last_checked_commit == head_commit:
                    repo_content = (
                        "--- CHANGES SINCE LAST CHECK ---\n"
                        f"No changes since commit {head_commit}.\n"
                    )
                else:
                    repo_content = await self._build_full_content(client, api_base, default_branch)

            record_github_repo_check(url, head_commit)
            return ScrapeResult(
                url=url,
                title=title,
                content=f"{repo_summary}\n{repo_content}",
                status="success",
            )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping GitHub {url}: {e}")
            return self._create_failed_result(url, f"GitHub API Error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error scraping GitHub {url}: {e}")
            return self._create_failed_result(url, f"Unexpected Error: {e}")

    def _build_repo_summary(
        self,
        owner: str,
        repo: str,
        repo_data: dict[str, Any],
        default_branch: str,
        head_commit: str,
        last_checked_commit: str | None,
    ) -> str:
        description = repo_data.get("description") or "No description provided."
        language = repo_data.get("language") or "Unknown"
        return (
            "--- REPOSITORY ---\n"
            f"Name: {owner}/{repo}\n"
            f"Description: {description}\n"
            f"Default branch: {default_branch}\n"
            f"Primary language: {language}\n"
            f"Latest commit: {head_commit}\n"
            f"Previously checked commit: {last_checked_commit or 'None'}\n"
        )

    async def _build_full_content(self, client: httpx.AsyncClient, api_base: str, default_branch: str) -> str:
        tree_resp = await client.get(f"{api_base}/git/trees/{default_branch}?recursive=1")
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()
        tree_items = tree_data.get("tree", [])

        structure_lines = []
        file_sections = []
        total_chars = 0
        fetched_files = 0
        skipped_files = 0

        for item in tree_items:
            path = item.get("path", "")
            item_type = item.get("type", "")
            icon = "📁" if item_type == "tree" else "📄"
            structure_lines.append(f"{icon} {path}")

            if item_type != "blob" or not self._should_fetch_file(path, item.get("size", 0)):
                if item_type == "blob":
                    skipped_files += 1
                continue
            if fetched_files >= MAX_REPO_FILES or total_chars >= MAX_TOTAL_CONTENT_CHARS:
                skipped_files += 1
                continue

            blob_text = await self._fetch_blob_text(client, api_base, item.get("sha", ""))
            if not blob_text:
                skipped_files += 1
                continue

            remaining_chars = MAX_TOTAL_CONTENT_CHARS - total_chars
            trimmed_text = blob_text[:remaining_chars]
            file_sections.append(f"### {path}\n{trimmed_text}")
            total_chars += len(trimmed_text)
            fetched_files += 1

        content = "--- STRUCTURE ---\n" + "\n".join(structure_lines)
        if file_sections:
            content += "\n\n--- FILE CONTENTS ---\n" + "\n\n".join(file_sections)
        if skipped_files:
            content += (
                "\n\n--- SNAPSHOT NOTES ---\n"
                f"Skipped {skipped_files} files because they were binary, too large, or beyond snapshot limits.\n"
            )
        return content

    async def _build_incremental_content(
        self,
        client: httpx.AsyncClient,
        api_base: str,
        last_checked_commit: str,
        head_commit: str,
    ) -> str | None:
        compare_resp = await client.get(f"{api_base}/compare/{last_checked_commit}...{head_commit}")
        if compare_resp.status_code == 404:
            return None
        compare_resp.raise_for_status()
        compare_data = compare_resp.json()

        commit_lines = [
            f"- {commit.get('sha', '')[:7]} {commit.get('commit', {}).get('message', '').splitlines()[0]}"
            for commit in compare_data.get("commits", [])
            if commit.get("commit", {}).get("message")
        ]
        file_lines = []
        for file_info in compare_data.get("files", []):
            filename = file_info.get("filename", "")
            status = file_info.get("status", "modified")
            patch = file_info.get("patch", "Patch unavailable.")
            additions = file_info.get("additions", 0)
            deletions = file_info.get("deletions", 0)
            file_lines.append(
                f"### {filename}\n"
                f"Status: {status}\n"
                f"Additions: {additions}\n"
                f"Deletions: {deletions}\n"
                f"Patch:\n{patch}"
            )

        sections = [f"--- CHANGES SINCE LAST CHECK ---\nFrom {last_checked_commit} to {head_commit}"]
        if commit_lines:
            sections.append("--- COMMITS ---\n" + "\n".join(commit_lines))
        if file_lines:
            sections.append("--- CHANGED FILES ---\n" + "\n\n".join(file_lines))
        else:
            sections.append("--- CHANGED FILES ---\nGitHub reported no file-level changes.")
        return "\n\n".join(sections)

    async def _fetch_blob_text(self, client: httpx.AsyncClient, api_base: str, blob_sha: str) -> str:
        if not blob_sha:
            return ""

        blob_resp = await client.get(f"{api_base}/git/blobs/{blob_sha}")
        blob_resp.raise_for_status()
        blob_data = blob_resp.json()
        content = blob_data.get("content", "")
        encoding = blob_data.get("encoding")
        if encoding != "base64" or not content:
            return ""

        try:
            decoded = b64decode(content, validate=True)
        except (BinasciiError, ValueError):
            return ""

        if len(decoded) > MAX_BLOB_BYTES:
            return ""

        try:
            return decoded.decode("utf-8")
        except UnicodeDecodeError:
            return ""

    def _should_fetch_file(self, path: str, size: int) -> bool:
        file_name = path.rsplit("/", maxsplit=1)[-1]
        lower_name = file_name.lower()
        if size > MAX_BLOB_BYTES:
            return False
        name_root, separator, extension = lower_name.rpartition(".")
        has_extension = bool(separator and name_root)
        if separator:
            dotted_extension = f".{extension}"
            if dotted_extension in _BINARY_EXTENSIONS:
                return False
        return lower_name in _TEXT_FILE_NAMES or has_extension
