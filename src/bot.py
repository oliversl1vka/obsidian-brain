import logging
import asyncio
import os
import sys
from datetime import time as dt_time, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

try:
    from telegram.ext import JobQueue as _JobQueue
    _job_queue = _JobQueue()
except (RuntimeError, ImportError):
    _job_queue = None
from src.config import settings
from src.utils.logging import setup_logging
from src.pipeline import process_link, PipelineResult
from src.storage.writer import get_link_stats
from src.digest import run_digest

BRAIN_ASSESS_JOB = "brain_assess"
BRAIN_DEBOUNCE_SECONDS = 10.0

# Set in main() after git bootstrap. When False, brain writes/assessment/commit are skipped
# but link saving still works. Allows the bot to run on hosts without git/credentials.
_brain_enabled = False

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    if update.effective_user.id != settings.telegram_user_id:
        return

    await update.message.reply_text(
        "Hi! I'm LinkStash. Send me a link (or a list of links, one per line) and I'll summarize and store them for you."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply with saved link counts and 3 most recent entries."""
    if update.effective_user.id != settings.telegram_user_id:
        return

    stats = get_link_stats()
    total = stats["total"]
    by_category = stats["by_category"]
    recent = stats["recent"]

    lines = [f"📚 *LinkStash Status* — {total} links saved\n"]
    if by_category:
        lines.append("*By category:*")
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            lines.append(f"  • {cat}: {count}")
    if recent:
        lines.append("\n*3 most recent:*")
        for entry in recent:
            lines.append(f"  • [{entry['title']}]({entry['url']}) — {entry['category']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def _send_processing_result(bot, chat_id: int, url: str) -> PipelineResult | None:
    """Process a single URL, send the result to Telegram, and return the PipelineResult."""
    try:
        result = await process_link(url)

        if result.status == "success":
            if result.notify:
                msg = f"✅ **{result.title}** stored in **{result.category}**."
                await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                if result.summary and result.summary != "scrape_failed":
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"📝 **Relevant Summary**:\n{result.summary}",
                        parse_mode="Markdown",
                    )
            else:
                await bot.send_message(chat_id=chat_id, text="🗑️ Not relevant — saved to bin.")
        elif result.status == "duplicate":
            await bot.send_message(chat_id=chat_id, text=f"⏭️ {url} was already processed. Skipped.")
        else:
            summary = result.summary or ""
            if summary.startswith("rate_limit_error"):
                msg = f"⏳ Rate limited while processing {url}. Try again in a moment."
            elif summary.startswith("scrape_error"):
                msg = f"🌐 Could not fetch {url}. The page may be down or require login."
            elif summary.startswith("llm_error"):
                msg = f"🤖 LLM error processing {url}. Check your OpenAI API key/quota."
            else:
                msg = f"❌ Failed to process {url}.\nReason: {summary}"
            await bot.send_message(chat_id=chat_id, text=msg)
        return result
    except Exception as e:
        logger.exception(f"Bot error processing {url}: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Fatal error processing {url}: {str(e)}")
        return None


async def _write_result_to_brain(result: PipelineResult, chat_id: int) -> bool:
    """Format and write a successful pipeline result to the brain vault. Returns True on success."""
    try:
        from src.brain.formatter import EntryFormatter
        from src.brain.writer import BrainWriter

        writer = BrainWriter()
        existing_titles = writer.get_all_entry_titles()
        formatter = EntryFormatter()
        formatted = await formatter.format_entry(result, existing_titles)
        writer.write_entry(formatted)
        return True
    except Exception as e:
        logger.exception(f"Brain pipeline error for {result.url}: {e}")
        return False


def _schedule_brain_assess(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Debounced schedule of the brain assessment job."""
    if context.job_queue is None:
        return
    for job in context.job_queue.get_jobs_by_name(BRAIN_ASSESS_JOB):
        job.schedule_removal()
    context.job_queue.run_once(
        brain_assess_job,
        when=BRAIN_DEBOUNCE_SECONDS,
        data={"chat_id": chat_id},
        name=BRAIN_ASSESS_JOB,
    )


async def brain_assess_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run brain assessment and send Telegram inline keyboard for approval."""
    chat_id = context.job.data["chat_id"]
    try:
        from src.brain.assessor import BrainAssessor

        assessor = BrainAssessor()
        result = await assessor.assess_recent_changes()
        if result is None:
            logger.info("Brain assess: no changes pending.")
            return

        msg = result.format_telegram_message()
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Commit & Push", callback_data="brain_commit"),
            InlineKeyboardButton("❌ Discard", callback_data="brain_discard"),
        ]])
        await context.bot.send_message(
            chat_id=chat_id, text=msg, parse_mode="Markdown", reply_markup=keyboard
        )
    except Exception as e:
        logger.exception(f"brain_assess_job failed: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Brain assessment error: {e}")


async def brain_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callbacks for brain commit/discard."""
    query = update.callback_query
    if update.effective_user.id != settings.telegram_user_id:
        await query.answer()
        return

    await query.answer()
    action = query.data

    try:
        from src.brain.git_ops import BrainGitOps

        ops = BrainGitOps()

        if action == "brain_commit":
            if not ops.has_changes():
                await query.edit_message_text("ℹ️ No brain changes to commit.")
                return

            # Build commit message from new files count
            from git import Repo
            repo = Repo(settings.brain_dir)
            new_entries = sum(
                1 for f in repo.untracked_files
                if f.startswith("Entries/")
            )
            commit_msg = f"brain: add {new_entries} entries via LinkStash"

            commit_result = ops.commit_brain(commit_msg)
            if not commit_result.success:
                await query.edit_message_text(f"❌ Commit failed: {commit_result.error}")
                return

            push_ok, push_err = ops.push_brain(settings.git_remote, settings.git_branch)
            total = ops.get_entry_count()
            if push_ok:
                brain_label = settings.brain_dir.name or str(settings.brain_dir)
                summary = (
                    f"✓ Brain updated: `{commit_result.commit_sha}`\n"
                    f"  +{new_entries} entries\n"
                    f"  {brain_label}/ @ {total} total entries"
                )
            else:
                summary = (
                    f"⚠️ Committed `{commit_result.commit_sha}` but push failed:\n{push_err}"
                )
            await query.edit_message_text(summary, parse_mode="Markdown")

        elif action == "brain_discard":
            ops.discard_brain_changes()
            await query.edit_message_text("🗑️ Brain changes discarded.")
    except Exception as e:
        logger.exception(f"brain_callback error: {e}")
        await query.edit_message_text(f"❌ Error: {e}")


async def process_link_job(context: ContextTypes.DEFAULT_TYPE):
    """Background job to process a single URL."""
    url = context.job.data["url"]
    chat_id = context.job.data["chat_id"]
    result = await _send_processing_result(context.bot, chat_id, url)

    if result and result.status == "success" and result.notify and _brain_enabled:
        if await _write_result_to_brain(result, chat_id):
            _schedule_brain_assess(context, chat_id)


async def _delayed_process_link(bot, chat_id: int, url: str, delay_seconds: float) -> None:
    """Fallback processor when PTB JobQueue is unavailable."""
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    result = await _send_processing_result(bot, chat_id, url)
    if result and result.status == "success" and result.notify and _brain_enabled:
        await _write_result_to_brain(result, chat_id)


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger the daily digest run."""
    if update.effective_user.id != settings.telegram_user_id:
        return
    await update.message.reply_text("🗓 Running digest...")
    results = await run_digest()
    notify = [r for r in results if r.status == "success" and r.notify]
    if _brain_enabled:
        for r in notify:
            await _write_result_to_brain(r, update.effective_chat.id)
    summary = (
        f"Digest complete: {len(notify)} saved, "
        f"{len([r for r in results if r.status == 'duplicate'])} duplicates, "
        f"{len([r for r in results if r.status == 'failed'])} failed."
    )
    await update.message.reply_text(summary)
    if notify and _brain_enabled:
        _schedule_brain_assess(context, update.effective_chat.id)


async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled daily digest job."""
    chat_id = settings.telegram_user_id
    try:
        await context.bot.send_message(chat_id=chat_id, text="🗓 Running scheduled daily digest...")
        results = await run_digest()
        notify = [r for r in results if r.status == "success" and r.notify]
        for r in notify:
            await _write_result_to_brain(r, chat_id)
        summary = (
            f"Daily digest: {len(notify)} saved, "
            f"{len([r for r in results if r.status == 'duplicate'])} duplicates, "
            f"{len([r for r in results if r.status == 'failed'])} failed."
        )
        await context.bot.send_message(chat_id=chat_id, text=summary)
        if notify and _brain_enabled:
            _schedule_brain_assess(context, chat_id)
    except Exception as e:
        logger.exception(f"daily_digest_job failed: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected Telegram handler errors."""
    logger.exception("Unhandled Telegram error", exc_info=context.error)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming messages as links."""
    # Ensure it's the authorized user
    if update.effective_user.id != settings.telegram_user_id:
        logger.warning(f"Unauthorized access attempt by user: {update.effective_user.id}")
        return

    text = update.message.text
    if not text:
        return
        
    # Split text by newlines and filter empty lines
    urls = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not urls:
        await update.message.reply_text("Please provide valid URLs.")
        return
        
    # Acknowledge receipt immediately
    await update.message.reply_text(f"Got {len(urls)} link(s), queuing for processing...")
    
    use_job_queue = context.job_queue is not None
    if not use_job_queue:
        logger.warning("PTB JobQueue is unavailable; falling back to asyncio task scheduling.")

    # Enqueue each URL as a separate background job
    for i, url in enumerate(urls):
        if not url.startswith("http"):
            await update.message.reply_text(f"❌ '{url}' is not a valid HTTP/HTTPS URL. Skipped.")
            continue

        delay_seconds = i * 2.0
        if use_job_queue:
            context.job_queue.run_once(
                process_link_job,
                when=delay_seconds,
                data={"url": url, "chat_id": update.effective_chat.id},
                name=f"process_link_{update.effective_message.message_id}_{i}",
            )
        else:
            context.application.create_task(
                _delayed_process_link(context.bot, update.effective_chat.id, url, delay_seconds)
            )

def main():
    """Start the bot."""
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        sys.exit(1)
        
    if not settings.telegram_user_id:
        logger.error("TELEGRAM_USER_ID is not set.")
        sys.exit(1)

    # Brain pipeline requires a working git repo + (for push) credentials.
    # If bootstrap fails or BRAIN_ENABLED=false, link saving still works fine.
    global _brain_enabled
    if os.environ.get("BRAIN_ENABLED", "true").lower() in ("false", "0", "no"):
        logger.info("BRAIN_ENABLED=false — brain features disabled by env.")
        _brain_enabled = False
    else:
        from src.brain.git_bootstrap import bootstrap_brain_git
        _brain_enabled = bootstrap_brain_git()
        logger.info(f"Brain features enabled: {_brain_enabled}")

    builder = ApplicationBuilder().token(settings.telegram_bot_token)
    if _job_queue is not None:
        builder = builder.job_queue(_job_queue)
    application = builder.build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("digest", digest_command))
    application.add_handler(CallbackQueryHandler(brain_callback, pattern="^brain_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Schedule daily digest if job queue is available
    if application.job_queue is not None:
        try:
            hour_str, minute_str = settings.digest_schedule.split(":")
            digest_time = dt_time(hour=int(hour_str), minute=int(minute_str), tzinfo=timezone.utc)
            application.job_queue.run_daily(
                daily_digest_job, time=digest_time, name="daily_digest"
            )
            logger.info(f"Daily digest scheduled at {settings.digest_schedule} UTC")
        except Exception as e:
            logger.error(f"Failed to schedule daily digest: {e}")
    else:
        logger.warning("JobQueue unavailable — daily digest will not run automatically.")

    logger.info("Starting LinkStash Bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
