import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from src.session_manager import session_manager
from src.handlers.group_handlers import is_authorized_user
from src import database

logger = logging.getLogger(__name__)


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually stop an active quiz session (Group or DM)."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    session = session_manager.get_session(chat.id)
    if not session or not session.is_active:
        pending = session_manager.get_pending_selection(chat.id)
        if pending:
            if not await is_authorized_user(update, context, pending["starter_id"]):
                await update.message.reply_text("⚠️ Only the quiz initiator or an admin can cancel!")
                return
            session_manager.clear_pending_selection(chat.id)
            await update.message.reply_text("🚫 Quiz setup cancelled.")
            return

        await update.message.reply_text("ℹ️ There is no active quiz running.")
        return

    # Check permission
    if not await is_authorized_user(update, context, session.starter_id):
        await update.message.reply_text("⚠️ Only the person who started this quiz or a group admin can stop it!")
        return

    # Remove active jobs for this chat
    current_jobs = context.job_queue.get_jobs_by_name(f"quiz_{chat.id}")
    for j in current_jobs:
        j.schedule_removal()

    session_manager.end_session(chat.id)
    await update.message.reply_text(
        f"🛑 *Quiz stopped by {user.first_name}.*\n"
        f"Type /quiz whenever you want to start a new game!",
        parse_mode=ParseMode.MARKDOWN
    )


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display leaderboard (Global in DM, Group in group chats)."""
    chat = update.effective_chat
    if not chat:
        return

    # 1. Private DM -> Show Global Solo Leaderboard
    if chat.type == ChatType.PRIVATE:
        leaders = database.get_global_solo_leaderboard(limit=10)
        if not leaders:
            await update.message.reply_text(
                "🌍 *ICSE 10TH GLOBAL SOLO LEADERBOARD* 🌍\n"
                "I am designed exclusively for ICSE 10TH.\n\n"
                "No solo quiz scores recorded yet!\n"
                "Play a quiz with /quiz to get ranked #1.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for rank, p in enumerate(leaders):
            name = p.get("first_name", "Student")
            username = p.get("username")
            display = f"@{username}" if username else name
            pts = p.get("solo_points", 0)
            played = p.get("solo_quizzes_played", 0)

            if rank < len(medals):
                medal = medals[rank]
                lines.append(f"{medal} *{rank + 1}. {display}* — {pts} pts ({played} quizzes)")
            else:
                lines.append(f"▫️ {rank + 1}. {display} — {pts} pts ({played} quizzes)")

        keyboard = [
            [InlineKeyboardButton("🏆 View Tournament Champions", callback_data="lb_tourn")],
            [InlineKeyboardButton("🚀 Play Solo Quiz", callback_data="menu_solo_quiz")]
        ]
        await update.message.reply_text(
            f"🌍 *ICSE 10TH GLOBAL SOLO LEADERBOARD* 🌍\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"🏆 *Top 10 Solo Scholars Worldwide:*\n"
            f"{chr(10).join(lines)}\n\n"
            f"💡 *Points earned from personal DM quizzes.*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 2. Group Chats -> Show Group All-Time Leaderboard
    top_players = database.get_group_leaderboard(chat.id, limit=10)
    if not top_players:
        await update.message.reply_text(
            "📊 *GROUP ALL-TIME LEADERBOARD*\n\n"
            "No quizzes have been completed in this group yet!\n"
            "Type /quiz to play the first round.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for rank, p in enumerate(top_players):
        name = p.get("first_name", "Player")
        username = p.get("username")
        display = f"@{username}" if username else name
        points = p.get("points", 0)
        played = p.get("quizzes_played", 0)

        if rank < len(medals):
            medal = medals[rank]
            lines.append(f"{medal} *{rank + 1}. {display}* — {points} pts ({played} games)")
        else:
            lines.append(f"▫️ {rank + 1}. {display} — {points} pts ({played} games)")

    leaderboard_text = "\n".join(lines)
    keyboard = [
        [InlineKeyboardButton("🌍 View Global Leaderboards", callback_data="menu_leaderboard")]
    ]
    await update.message.reply_text(
        f"🏆 *GROUP ALL-TIME HALL OF FAME* 🏆\n"
        f"📍 Group: *{chat.title}*\n\n"
        f"{leaderboard_text}\n\n"
        f"Keep playing with /quiz to climb the ranks!",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display personal statistics for the calling user (DM or Group)."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    is_dm = (chat.type == ChatType.PRIVATE)
    stats = database.get_user_stats(None if is_dm else chat.id, user.id)

    solo_pts = stats.get("solo_points", 0) if stats else 0
    solo_played = stats.get("solo_played", 0) if stats else 0
    solo_rank = stats.get("solo_rank", "-") if stats else "-"

    tourn_pts = stats.get("tournament_points", 0) if stats else 0
    tourn_wins = stats.get("tournament_wins", 0) if stats else 0
    tourn_played = stats.get("tournament_played", 0) if stats else 0
    tourn_rank = stats.get("tournament_rank", "-") if stats else "-"

    if is_dm:
        await update.message.reply_text(
            f"👤 *ICSE 10TH STUDENT PROFILE* 👤\n"
            f"Name: *{user.first_name}*\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"🎯 *Solo Practice Record:*\n"
            f"• Solo Points: *{solo_pts} pts*\n"
            f"• Quizzes Completed: *{solo_played}*\n"
            f"• Worldwide Solo Rank: *#{solo_rank}*\n\n"
            f"⚔️ *Group Tournament Record:*\n"
            f"• Tournament Wins: 🏆 *{tourn_wins} Wins*\n"
            f"• Tournament Points: *{tourn_pts} pts*\n"
            f"• Tournaments Played: *{tourn_played}*\n"
            f"• Worldwide Tournament Rank: *#{tourn_rank}*\n\n"
            f"Keep practicing daily to top the ICSE boards! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        group_pts = stats.get("group_points", 0) if stats else 0
        group_played = stats.get("group_played", 0) if stats else 0
        group_rank = stats.get("group_rank", "-") if stats else "-"
        await update.message.reply_text(
            f"👤 *PLAYER PROFILE: {user.first_name}*\n\n"
            f"📍 *This Group:*\n"
            f"• Group Rank: #{group_rank}\n"
            f"• Points Earned: {group_pts} pts\n"
            f"• Quizzes Played: {group_played}\n\n"
            f"🌍 *Global Career:*\n"
            f"• Solo Points: {solo_pts} pts (Rank #{solo_rank})\n"
            f"• Tournament Wins: 🏆 {tourn_wins} (Rank #{tourn_rank})\n",
            parse_mode=ParseMode.MARKDOWN
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show instructions and list of available bot commands."""
    help_text = (
        "📖 *ICSE 10TH QUIZ BOT COMMAND GUIDE*\n"
        "I am designed exclusively for ICSE 10TH.\n\n"
        "🎮 *Available Commands:*\n"
        "• /start — Open the interactive dashboard (in DM) or start a quiz\n"
        "• /quiz — Open ICSE subject & topic selection (Solo in DM, Multiplayer in Groups)\n"
        "• /dailyquiz or /daily — Pull 1 untimed question from each of the 9 ICSE subjects\n"
        "• /leaderboard — View Global Solo Leaderboard (in DM) or Group Champions (in groups)\n"
        "• /mystats — Check your points, rank, and tournament wins\n"
        "• /stopquiz — Stop the active quiz round\n"
        "• /help — Show this command manual\n\n"
        "📚 *All 9 ICSE Subjects Covered:*\n"
        "PHYSICS, MATHS, BIOLOGY, CHEMISTRY, HISTORY, GEOGRAPHY, COMPUTER, ENGLISH 1, ENGLISH 2 (Prose, Poetry, Julius Caesar)\n\n"
        "⚡ *Solo DM Pacing:* In personal DM chats, polls advance automatically as soon as you vote!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
