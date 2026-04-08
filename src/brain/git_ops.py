import logging
from dataclasses import dataclass

from src.brain.git_utils import sanitize_git_error_message
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CommitResult:
    success: bool
    commit_sha: str = ""
    message: str = ""
    error: str = ""


class BrainGitOps:
    def __init__(self):
        from git import Repo
        self.brain_dir = settings.brain_dir
        self.repo = Repo(self.brain_dir)

    def has_changes(self) -> bool:
        """True if there are uncommitted changes in the configured brain repo."""
        try:
            return bool(self.repo.git.status("--porcelain").strip())
        except Exception:
            pass
        return False

    def stage_brain(self) -> None:
        """Stage all changes in the configured brain repo."""
        self.repo.git.add("--all")

    def commit_brain(self, message: str) -> CommitResult:
        """Stage and commit all brain changes."""
        try:
            if not self.has_changes():
                return CommitResult(success=False, error="No changes to commit.")
            self.stage_brain()
            commit = self.repo.index.commit(message)
            return CommitResult(success=True, commit_sha=commit.hexsha[:7], message=message)
        except Exception as e:
            error = sanitize_git_error_message(e)
            logger.error("Git commit failed: %s", error)
            return CommitResult(success=False, error=error)

    def push_brain(self, remote: str = "origin", branch: str = "master") -> tuple[bool, str]:
        """Push to remote. Returns (success, error_message)."""
        try:
            self.repo.git.push(remote, branch)
            return True, ""
        except Exception as e:
            error = sanitize_git_error_message(e)
            logger.error("Git push failed: %s", error)
            return False, error

    def discard_brain_changes(self) -> None:
        """Revert all uncommitted brain changes in the dedicated brain repo."""
        try:
            try:
                self.repo.git.reset("--hard", "HEAD")
            except Exception as e:
                logger.warning(
                    "Reset during discard failed (may be no commits yet): %s",
                    sanitize_git_error_message(e),
                )
            for f in list(self.repo.untracked_files):
                target = self.brain_dir / f
                try:
                    if target.is_dir():
                        for child in sorted(target.rglob("*"), reverse=True):
                            if child.is_file():
                                child.unlink()
                            elif child.is_dir():
                                child.rmdir()
                        target.rmdir()
                    else:
                        target.unlink()
                except FileNotFoundError:
                    pass
        except Exception as e:
            logger.error("Git discard failed: %s", sanitize_git_error_message(e))

    def get_entry_count(self) -> int:
        entries_dir = self.brain_dir / "Entries"
        if not entries_dir.exists():
            return 0
        return sum(1 for _ in entries_dir.glob("*.md"))
