import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.brain.formatter import FormattedEntry
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WrittenEntry:
    entry_path: Path
    topic_path: Path
    title: str
    date: str
    category: str


class BrainWriter:
    def __init__(self):
        self.brain_dir: Path = settings.brain_dir

    def write_entry(self, entry: FormattedEntry) -> WrittenEntry:
        """Write a knowledge entry to the brain vault."""
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        (self.brain_dir / "Entries").mkdir(exist_ok=True)
        (self.brain_dir / "Topics").mkdir(exist_ok=True)
        (self.brain_dir / "Logs").mkdir(exist_ok=True)
        self._ensure_home_page()

        slug = _slugify(entry.title)
        entry_filename = f"{entry.date}-{slug}.md"
        entry_path = self.brain_dir / "Entries" / entry_filename

        tags_str = " ".join(f"#{t}" for t in entry.tags) if entry.tags else ""
        topic_link = f"[[Topics/{entry.category}]]"
        see_also_parts = [f"[[{t}]]" for t in entry.see_also] + [topic_link]
        see_also_str = " · ".join(see_also_parts)

        # Write individual entry file
        entry_content = (
            f"---\n"
            f"date: {entry.date}\n"
            f"category: {entry.category}\n"
            f"source: {entry.url}\n"
            f"tags: [{', '.join(entry.tags)}]\n"
            f"---\n\n"
            f"## [{entry.date}] {entry.title}\n\n"
            f"**Context:** {entry.context}\n"
            f"**Insight:** {entry.insight}\n"
            f"**Application:** {entry.application}\n"
            f"**Tags:** {tags_str}\n"
            f"**Source:** [{entry.title}]({entry.url})\n"
            f"See also: {see_also_str}\n"
        )
        entry_path.write_text(entry_content, encoding="utf-8")

        # Append to topic page
        topic_path = self.brain_dir / "Topics" / f"{entry.category}.md"
        topic_block = (
            f"\n### [{entry.date}] {entry.title}\n"
            f"**Insight:** {entry.insight}\n"
            f"**Source:** [{entry.title}]({entry.url}) · [[Entries/{entry_filename[:-3]}]]\n\n"
            f"---\n"
        )
        if not topic_path.exists():
            topic_path.write_text(
                f"# {entry.category}\n\n> Compiled knowledge on this topic.\n\n## Entries\n",
                encoding="utf-8",
            )
        with open(topic_path, "a", encoding="utf-8") as f:
            f.write(topic_block)

        # Append to index.md (chronological, oldest first)
        index_path = self.brain_dir / "index.md"
        if not index_path.exists():
            index_path.write_text(
                "# Brain Index\n\n<!-- entries below — oldest first, newest at bottom -->\n",
                encoding="utf-8",
            )
        with open(index_path, "a", encoding="utf-8") as f:
            f.write(
                f"- [{entry.date}] [{entry.title}]({entry.url}) — **{entry.category}** · [[Entries/{entry_filename[:-3]}]]\n"
            )

        # Update Home.md recent section
        self._update_home(entry, entry_filename[:-3])

        logger.info(f"Brain entry written: {entry_path.name}")
        return WrittenEntry(
            entry_path=entry_path,
            topic_path=topic_path,
            title=entry.title,
            date=entry.date,
            category=entry.category,
        )

    def _update_home(self, entry: FormattedEntry, entry_slug: str) -> None:
        """Update the recently added section in Home.md (keep last 10)."""
        home_path = self.brain_dir / "Home.md"
        if not home_path.exists():
            return

        content = home_path.read_text(encoding="utf-8")
        new_line = f"- [{entry.date}] [[Entries/{entry_slug}|{entry.title}]] — {entry.category}\n"

        start_marker = "<!-- RECENT_START -->\n"
        end_marker = "<!-- RECENT_END -->"

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return

        recent_section = content[start_idx + len(start_marker) : end_idx]
        lines = [line for line in recent_section.splitlines(keepends=True) if line.strip()]
        lines = [new_line] + lines[:9]  # newest first, keep 10 total

        updated = (
            content[: start_idx + len(start_marker)]
            + "".join(lines)
            + content[end_idx:]
        )
        home_path.write_text(updated, encoding="utf-8")

    def _ensure_home_page(self) -> None:
        home_path = self.brain_dir / "Home.md"
        if home_path.exists():
            return

        topics = "\n".join(f"- [[Topics/{category}]]" for category in settings.categories)
        home_path.write_text(
            (
                "# LinkStash Brain\n\n"
                "> Personal knowledge intelligence vault. Links compiled into structured knowledge via AI.\n\n"
                "## Recently Added\n\n"
                "<!-- RECENT_START -->\n"
                "<!-- RECENT_END -->\n\n"
                "## Topics\n"
                f"{topics}\n\n"
                "## Index\n"
                "[[index]] — Full chronological catalog of all entries.\n"
            ),
            encoding="utf-8",
        )

    def get_all_entry_titles(self) -> list[str]:
        """Return titles of the 100 most recent entries (for wikilink candidates)."""
        entries_dir = self.brain_dir / "Entries"
        if not entries_dir.exists():
            return []
        heading_re = re.compile(r"^## \[\d{4}-\d{2}-\d{2}\] (.+)$", re.MULTILINE)
        titles = []
        for md_file in sorted(entries_dir.glob("*.md"), reverse=True)[:100]:
            text = md_file.read_text(encoding="utf-8")
            match = heading_re.search(text)
            if match:
                titles.append(match.group(1))
        return titles

    def get_entry_count(self) -> int:
        entries_dir = self.brain_dir / "Entries"
        if not entries_dir.exists():
            return 0
        return sum(1 for _ in entries_dir.glob("*.md"))


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text[:60]
