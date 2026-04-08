import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BRAIN_DIR = "obsidian-brain"


@dataclass
class CommitResult:
    success: bool
    commit_sha: str = ""
    message: str = ""
    error: str = ""


class BrainGitOps:
    def __init__(self):
        from git import Repo
        self.repo = Repo(_PROJECT_ROOT)

    def has_changes(self) -> bool:
        """True if there are uncommitted changes (modified or untracked) in obsidian-brain/."""
        for f in self.repo.untracked_files:
            if f.startswith(_BRAIN_DIR + "/"):
                return True
        try:
            diff = self.repo.git.diff("HEAD", "--", _BRAIN_DIR)
            if diff.strip():
                return True
        except Exception:
            pass
        return False

    def stage_brain(self) -> None:
        """Stage all changes in obsidian-brain/."""
        self.repo.git.add(_BRAIN_DIR)

    def commit_brain(self, message: str) -> CommitResult:
        """Stage and commit all brain changes."""
        try:
            if not self.has_changes():
                return CommitResult(success=False, error="No changes to commit.")
            self.stage_brain()
            commit = self.repo.index.commit(message)
            return CommitResult(success=True, commit_sha=commit.hexsha[:7], message=message)
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return CommitResult(success=False, error=str(e))

    def push_brain(self, remote: str = "origin", branch: str = "master") -> tuple[bool, str]:
        """Push to remote. Returns (success, error_message)."""
        try:
            self.repo.git.push(remote, branch)
            return True, ""
        except Exception as e:
            logger.error(f"Git push failed: {e}")
            return False, str(e)

    def discard_brain_changes(self) -> None:
        """Revert all uncommitted brain changes (modified + new untracked files)."""
        try:
            for f in list(self.repo.untracked_files):
                if f.startswith(_BRAIN_DIR + "/"):
                    target = _PROJECT_ROOT / f
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass
            try:
                self.repo.git.checkout("--", _BRAIN_DIR)
            except Exception as e:
                logger.warning(f"Checkout during discard failed (may be no tracked changes): {e}")
        except Exception as e:
            logger.error(f"Git discard failed: {e}")

    def get_entry_count(self) -> int:
        entries_dir = _PROJECT_ROOT / _BRAIN_DIR / "Entries"
        if not entries_dir.exists():
            return 0
        return sum(1 for _ in entries_dir.glob("*.md"))
