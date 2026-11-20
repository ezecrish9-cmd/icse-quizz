import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from src.quiz_manager import quiz_manager
from src.session_manager import session_manager
from src import database

logger = logging.getLogger(__name__)


def build_main_dashboard_markup(bot_username: str) -> InlineKeyboardMarkup:
    add_group_url = f"https://t.me/{bot_username}?startgroup=true"
    keyboard = [
        [
            InlineKeyboardButton("🚀 Play Solo Quiz", callback_data="menu_solo_quiz"),
            InlineKeyboardButton("📅 Daily Quiz Pack", callback_data="menu_daily_quiz")
        ],
        [
            InlineKeyboardButton("🏆 Global Leaderboards", callback_data="menu_leaderboard"),
            InlineKeyboardButton("👤 My Performance Profile", callback_data="menu_my_profile")
        ],
        [
            InlineKeyboardButton("➕ Add Me to a Telegram Group", url=add_group_url)
        ],
        [
            InlineKeyboardButton("📖 Syllabus & Help", callback_data="menu_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_dm_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to /start in private DM with the interactive dashboard."""
    chat = update.effective_chat
    user = update.effective_user

    if not chat or chat.type != ChatType.PRIVATE:
        return

    bot_info = await context.bot.get_me()
    reply_markup = build_main_dashboard_markup(bot_info.username)

    welcome_text = (
        f"👋 *Hello {user.first_name}!*\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"🎯 Welcome to your personal *ICSE Class 10 Study & Quiz Hub*!\n"
        f"Practice questions across all 9 ICSE subjects, track your progress, "
        f"and compete on the worldwide Solo & Tournament Global Leaderboards.\n\n"
        f"👉 *Select an option below to begin:*"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_menu_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to the main dashboard menu."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    bot_info = await context.bot.get_me()
    reply_markup = build_main_dashboard_markup(bot_info.username)

    welcome_text = (
        f"👋 *Hello {user.first_name}!*\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"🎯 Welcome to your personal *ICSE Class 10 Study & Quiz Hub*!\n"
        f"Practice questions across all 9 ICSE subjects, track your progress, "
        f"and compete on the worldwide Solo & Tournament Global Leaderboards.\n\n"
        f"👉 *Select an option below to begin:*"
    )
    await query.edit_message_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_menu_solo_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open subject selection for solo quiz in DM."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    # Check if a quiz is currently active
    active_session = session_manager.get_session(chat.id)
    if active_session and active_session.is_active:
        await query.answer("A quiz is already active! Finish or type /stopquiz", show_alert=True)
        return

    subjects = quiz_manager.get_subjects()
    session_manager.set_pending_selection(chat.id, user.id, user.first_name)

    keyboard = []
    row = []
    for idx, subject in enumerate(subjects):
        row.append(InlineKeyboardButton(f"📚 {subject}", callback_data=f"sub:{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🎯 *ICSE 10TH SOLO PRACTICE QUIZ*\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"⚡ *Mode:* Instant progression upon answering\n\n"
        f"👉 *Select an ICSE Subject to begin:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_menu_daily_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Launch the untimed daily quiz pack in DM."""
    query = update.callback_query
    await query.answer("Generating Daily Quiz Pack...")

    from src.handlers.daily_handlers import daily_quiz_command
    await daily_quiz_command(update, context)


async def handle_menu_leaderboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the Global Solo Leaderboard by default."""
    query = update.callback_query
    await query.answer()
    await render_solo_leaderboard(query)


async def handle_lb_solo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle view to Global Solo Leaderboard."""
    query = update.callback_query
    await query.answer()
    await render_solo_leaderboard(query)


async def handle_lb_tourn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle view to Global Tournament Leaderboard."""
    query = update.callback_query
    await query.answer()
    await render_tournament_leaderboard(query)


async def render_solo_leaderboard(query) -> None:
    """Render the top 10 Solo players worldwide."""
    leaders = database.get_global_solo_leaderboard(limit=10)

    if not leaders:
        text = (
            f"🌍 *ICSE 10TH GLOBAL SOLO LEADERBOARD* 🌍\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"No solo quiz scores recorded yet!\n"
            f"Play your first solo quiz now to claim #1 rank worldwide."
        )
    else:
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

        text = (
            f"🌍 *ICSE 10TH GLOBAL SOLO LEADERBOARD* 🌍\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"🏆 *Top 10 Solo Scholars Worldwide:*\n"
            f"{chr(10).join(lines)}\n\n"
            f"💡 *Points are earned by solving ICSE quizzes in personal DM chat.*"
        )

    keyboard = [
        [InlineKeyboardButton("🏆 View Tournament Champions", callback_data="lb_tourn")],
        [InlineKeyboardButton("🚀 Play Solo Quiz", callback_data="menu_solo_quiz")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))


async def render_tournament_leaderboard(query) -> None:
    """Render the top 10 Tournament champions worldwide."""
    champions = database.get_global_tournament_leaderboard(limit=10)

    if not champions:
        text = (
            f"🏆 *ICSE 10TH GLOBAL TOURNAMENT LEADERBOARD* 🏆\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"No group tournament wins recorded yet!\n"
            f"Add the bot to your study group and win tournaments to get ranked."
        )
    else:
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for rank, p in enumerate(champions):
            name = p.get("first_name", "Champion")
            username = p.get("username")
            display = f"@{username}" if username else name
            wins = p.get("tournament_wins", 0)
            pts = p.get("tournament_points", 0)

            if rank < len(medals):
                medal = medals[rank]
                lines.append(f"{medal} *{rank + 1}. {display}* — 🏆 {wins} Wins | {pts} pts")
            else:
                lines.append(f"▫️ {rank + 1}. {display} — 🏆 {wins} Wins | {pts} pts")

        text = (
            f"🏆 *ICSE 10TH GLOBAL TOURNAMENT LEADERBOARD* 🏆\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"⚔️ *Top 10 Group Tournament Champions Worldwide:*\n"
            f"{chr(10).join(lines)}\n\n"
            f"💡 *Wins are earned by finishing #1 in group quiz tournaments.*"
        )

    keyboard = [
        [InlineKeyboardButton("🎯 View Solo Champions", callback_data="lb_solo")],
        [InlineKeyboardButton("➕ Add Me to a Group", url=f"https://t.me/{(await query.bot.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_menu_my_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the student's personal report card and global stats."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    stats = database.get_user_stats(None, user.id)

    solo_pts = stats.get("solo_points", 0) if stats else 0
    solo_played = stats.get("solo_played", 0) if stats else 0
    solo_rank = stats.get("solo_rank", "-") if stats else "-"

    tourn_pts = stats.get("tournament_points", 0) if stats else 0
    tourn_wins = stats.get("tournament_wins", 0) if stats else 0
    tourn_played = stats.get("tournament_played", 0) if stats else 0
    tourn_rank = stats.get("tournament_rank", "-") if stats else "-"

    profile_text = (
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
        f"Keep practicing daily to master every ICSE subject! 🚀"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 Play Solo Quiz", callback_data="menu_solo_quiz")],
        [InlineKeyboardButton("🏆 Global Leaderboards", callback_data="menu_leaderboard")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_menu_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display syllabus breakdown and instructions."""
    query = update.callback_query
    await query.answer()

    help_text = (
        f"📖 *ICSE 10TH QUIZ BOT MANUAL*\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"📚 *All 9 Board Subjects Covered:*\n"
        f"• *PHYSICS:* Mechanics, Energy, Light, Sound, Electricity\n"
        f"• *MATHS:* Commercial Maths, Algebra, Geometry, Trigonometry\n"
        f"• *BIOLOGY:* Genetics, Cell Cycle, Plant & Human Physiology\n"
        f"• *CHEMISTRY:* Periodic Trends, Bonding, Metallurgy, Organic\n"
        f"• *HISTORY:* Indian National Movement, Contemporary World & UN\n"
        f"• *GEOGRAPHY:* Climate, Soils, Vegetation, Water Resources\n"
        f"• *COMPUTER:* Java OOP, Arrays, Strings\n"
        f"• *ENGLISH 2:* Prose, Poetry, Julius Caesar (Shakespeare)\n"
        f"• *ENGLISH 1:* Grammar, Prepositions, Sentence Transformation\n\n"
        f"🎮 *How to Use:*\n"
        f"• In DM: Tap *Play Solo Quiz* or *Daily Quiz Pack* anytime!\n"
        f"• In Groups: Type `/quiz` for a timed multiplayer tournament.\n"
        f"• Commands: `/quiz`, `/dailyquiz`, `/leaderboard`, `/mystats`, `/help`."
    )
    keyboard = [
        [InlineKeyboardButton("🚀 Play Solo Quiz Now", callback_data="menu_solo_quiz")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
