import os
import httpx
from src.scrapers.base import BaseScraper, ScrapeResult
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class GitHubScraper(BaseScraper):
    async def scrape(self, url: str) -> ScrapeResult:
        # url format: https://github.com/owner/repo
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) < 2:
                return self._create_failed_result(url, "Invalid GitHub repository URL")
                
            owner, repo = path_parts[0], path_parts[1]
            api_base = f"https://api.github.com/repos/{owner}/{repo}"
            
            github_token = os.environ.get("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
                # 1. Get Repo metadata
                repo_resp = await client.get(api_base)
                if repo_resp.status_code == 404:
                    return self._create_failed_result(url, "Repository not found or private")
                repo_resp.raise_for_status()
                repo_data = repo_resp.json()
                
                title = f"{owner}/{repo} - {repo_data.get('description', '')}"
                
                # 2. Get README
                readme_resp = await client.get(f"{api_base}/readme")
                readme_content = "No README found."
                if readme_resp.status_code == 200:
                    import base64
                    readme_json = readme_resp.json()
                    if 'content' in readme_json:
                        readme_content = base64.b64decode(readme_json['content']).decode('utf-8')
                        
                # 3. Get shallow tree for structure (max 2-3 levels)
                # For simplicity and speed, just get the default branch root tree
                default_branch = repo_data.get('default_branch', 'main')
                tree_resp = await client.get(f"{api_base}/git/trees/{default_branch}")
                
                structure = "Repository Structure (Root):\n"
                if tree_resp.status_code == 200:
                    tree_data = tree_resp.json()
                    for item in tree_data.get('tree', []):
                        icon = "📁" if item['type'] == 'tree' else "📄"
                        structure += f"{icon} {item['path']}\n"
                
                full_content = f"--- STRUCTURE ---\n{structure}\n--- README ---\n{readme_content}"
                
            return ScrapeResult(
                url=url,
                title=title,
                content=full_content,
                status="success"
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error scraping GitHub {url}: {e}")
            return self._create_failed_result(url, f"GitHub API Error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error scraping GitHub {url}: {e}")
            return self._create_failed_result(url, f"Unexpected Error: {e}")
