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

from src.brain.git_utils import sanitize_git_error_message
from src.config import settings

logger = logging.getLogger(__name__)


def bootstrap_brain_git() -> bool:
    """Prepare the local git repo for brain commits/pushes. Returns True on success."""
    from git import Repo

    brain_dir = settings.brain_dir
    git_dir = brain_dir / ".git"
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo_slug = os.environ.get("GIT_REPO_SLUG", "").strip()
    branch = os.environ.get("GIT_BRANCH", "master")
    brain_dir.mkdir(parents=True, exist_ok=True)

    # If .git is missing, initialize a dedicated brain repo.
    if not git_dir.exists():
        try:
            logger.info("No brain git repo found — initializing %s", brain_dir)
            repo = Repo.init(brain_dir)
            try:
                repo.git.checkout("-B", branch)
            except Exception as e:
                logger.warning("Could not check out %s: %s", branch, sanitize_git_error_message(e))
            logger.info("Initialized brain git repo in %s", brain_dir)
        except Exception as e:
            logger.warning(
                "Brain disabled: failed to initialize git repo: %s",
                sanitize_git_error_message(e),
            )
            return False
    else:
        try:
            repo = Repo(brain_dir)
        except Exception as e:
            logger.warning(
                "Brain disabled: could not open git repo: %s",
                sanitize_git_error_message(e),
            )
            return False

    # 1. Set committer identity (required for `git commit`)
    user_email = os.environ.get("GIT_USER_EMAIL", "linkstash-bot@users.noreply.github.com")
    user_name = os.environ.get("GIT_USER_NAME", "LinkStash Bot")
    try:
        with repo.config_writer() as cw:
            cw.set_value("user", "email", user_email)
            cw.set_value("user", "name", user_name)
    except Exception as e:
        logger.warning("Could not set git user identity: %s", sanitize_git_error_message(e))

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
            logger.info("Configured brain origin remote for %s with token auth.", repo_slug)
        except Exception as e:
            logger.warning("Could not configure origin remote: %s", sanitize_git_error_message(e))
            return False
    elif token and not repo_slug:
        logger.warning("GITHUB_TOKEN set but GIT_REPO_SLUG missing — continuing with local-only brain repo.")
    else:
        # No token: brain commits will succeed locally but push will fail.
        # We still allow brain ops so the user can develop locally without env vars.
        logger.info("No GITHUB_TOKEN set — brain commits will be local-only (push will fail).")

    # 3. Best-effort pull so we have the latest brain entries from prior runs
    if token and repo_slug:
        try:
            repo.remotes.origin.fetch()
            remote_ref = f"origin/{branch}"
            if remote_ref in [ref.name for ref in repo.refs]:
                repo.git.checkout("-B", branch, remote_ref)
                repo.git.reset("--hard", remote_ref)
                logger.info("Synced brain repo to %s.", remote_ref)
            else:
                logger.info("Brain remote %s has no %s yet; continuing with local branch.", repo_slug, branch)
        except Exception as e:
            logger.warning(
                "Initial git pull failed (continuing anyway): %s",
                sanitize_git_error_message(e),
            )

    return True
