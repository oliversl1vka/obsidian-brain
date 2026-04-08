"""Configure the git repo for runtime push (Railway / containers).

At startup we may need to:
  1. Verify that .git exists (BrainGitOps depends on it)
  2. Inject a GITHUB_TOKEN into the origin remote URL so `git push` can authenticate
  3. Set user.email / user.name so commits don't fail with "please tell me who you are"
  4. Optionally `git pull` to sync any brain entries committed from a previous container

Returns True if the brain pipeline is safe to enable, False otherwise.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def bootstrap_brain_git() -> bool:
    """Prepare the local git repo for brain commits/pushes. Returns True on success."""
    git_dir = _PROJECT_ROOT / ".git"
    if not git_dir.exists():
        logger.warning(
            "Brain disabled: .git directory not found at %s. "
            "On Railway this means the build did not include .git — "
            "ensure you are using the Dockerfile builder, not Nixpacks.",
            _PROJECT_ROOT,
        )
        return False

    try:
        from git import Repo
        repo = Repo(_PROJECT_ROOT)
    except Exception as e:
        logger.warning(f"Brain disabled: could not open git repo: {e}")
        return False

    # 1. Set committer identity (required for `git commit`)
    user_email = os.environ.get("GIT_USER_EMAIL", "linkstash-bot@users.noreply.github.com")
    user_name = os.environ.get("GIT_USER_NAME", "LinkStash Bot")
    try:
        with repo.config_writer() as cw:
            cw.set_value("user", "email", user_email)
            cw.set_value("user", "name", user_name)
    except Exception as e:
        logger.warning(f"Could not set git user identity: {e}")

    # 2. Inject GitHub token into origin URL if provided
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo_slug = os.environ.get("GIT_REPO_SLUG", "").strip()  # e.g. "oliversl1vka/LinkStash"

    if token and repo_slug:
        authed_url = f"https://x-access-token:{token}@github.com/{repo_slug}.git"
        try:
            if "origin" in [r.name for r in repo.remotes]:
                repo.remotes.origin.set_url(authed_url)
            else:
                repo.create_remote("origin", authed_url)
            logger.info(f"Configured origin remote for {repo_slug} with token auth.")
        except Exception as e:
            logger.warning(f"Could not configure origin remote: {e}")
            return False
    elif token and not repo_slug:
        logger.warning("GITHUB_TOKEN set but GIT_REPO_SLUG missing — cannot configure remote.")
        return False
    else:
        # No token: brain commits will succeed locally but push will fail.
        # We still allow brain ops so the user can develop locally without env vars.
        logger.info("No GITHUB_TOKEN set — brain commits will be local-only (push will fail).")

    # 3. Best-effort pull so we have the latest brain entries from prior runs
    if token and repo_slug:
        try:
            repo.remotes.origin.fetch()
            branch = os.environ.get("GIT_BRANCH", "master")
            repo.git.reset("--hard", f"origin/{branch}")
            logger.info(f"Synced local repo to origin/{branch}.")
        except Exception as e:
            logger.warning(f"Initial git pull failed (continuing anyway): {e}")

    return True
