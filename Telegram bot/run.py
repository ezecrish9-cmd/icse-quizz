import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from telegram.request import HTTPXRequest
from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    filters,
)

from src.config import TELEGRAM_BOT_TOKEN
from src.database import init_db
from src.quiz_manager import quiz_manager
from src.handlers.group_handlers import (
    start_quiz_command,
    handle_subject_callback,
    handle_topic_callback,
    handle_back_subjects_callback,
    handle_cancel_callback,
    handle_replay_callback,
)
from src.handlers.poll_handlers import handle_poll_answer
from src.handlers.control_handlers import (
    stop_quiz_command,
    leaderboard_command,
    mystats_command,
    help_command,
)
from src.handlers.dm_handlers import (
    handle_dm_start,
    handle_menu_main_callback,
    handle_menu_solo_quiz_callback,
    handle_menu_daily_quiz_callback,
    handle_menu_leaderboard_callback,
    handle_lb_solo_callback,
    handle_lb_tourn_callback,
    handle_menu_my_profile_callback,
    handle_menu_help_callback,
)
from src.handlers.daily_handlers import daily_quiz_command

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to pass cloud platform health checks (e.g. Render, Koyeb, Railway)."""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ICSE Quiz Bot is running successfully!")

    def log_message(self, format, *args):
        pass  # Suppress HTTP access logging


def start_health_check_server() -> None:
    """Start dummy web server if PORT environment variable is present (for free cloud web services)."""
    port_str = os.getenv("PORT")
    if port_str:
        try:
            port = int(port_str)
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logger.info(f"🌐 Cloud health-check server running on port {port}")
        except Exception as e:
            logger.warning(f"Could not start cloud health check server: {e}")


async def post_init(application) -> None:
    """Register command autocomplete lists with Telegram so typing '/' in groups or DM shows the commands."""
    group_commands = [
        BotCommand("quiz", "Start a live multiplayer ICSE quiz tournament"),
        BotCommand("dailyquiz", "Send daily 1-question pack from all 9 subjects"),
        BotCommand("leaderboard", "View group & global leaderboards"),
        BotCommand("mystats", "View your performance profile & points"),
        BotCommand("stopquiz", "Stop the current active quiz"),
        BotCommand("help", "View ICSE syllabus & bot command guide"),
    ]

    dm_commands = [
        BotCommand("start", "Open the ICSE 10th Study Dashboard"),
        BotCommand("quiz", "Play a solo practice quiz"),
        BotCommand("dailyquiz", "Get daily 1-question pack from all 9 subjects"),
        BotCommand("leaderboard", "View Worldwide Global Leaderboards"),
        BotCommand("mystats", "View your student report card & points"),
        BotCommand("stopquiz", "Stop the active solo quiz"),
        BotCommand("help", "View ICSE syllabus & bot command guide"),
    ]

    try:
        # Register for group chats
        await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        # Register for private DMs
        await application.bot.set_my_commands(dm_commands, scope=BotCommandScopeAllPrivateChats())
        # Fallback default
        await application.bot.set_my_commands(group_commands, scope=BotCommandScopeDefault())
        logger.info("✅ Telegram bot command menu registered successfully for groups and DMs.")
    except Exception as e:
        logger.warning(f"Could not register bot commands with Telegram: {e}")


def main():
    print("=" * 60)
    print("🚀 Initializing ICSE 10th Quiz Telegram Bot...")
    print("=" * 60)

    # 1. Initialize SQLite Database
    init_db()
    print("✅ Database initialized successfully.")

    # Start cloud web health check if PORT is provided
    start_health_check_server()

    # 2. Check loaded quizzes
    quiz_manager.load_quizzes()
    subjects = quiz_manager.get_subjects()
    print(f"✅ Loaded {len(subjects)} subjects:")
    for sub in subjects:
        topics = quiz_manager.get_topics(sub)
        topic_names = ", ".join([t["topic"] for t in topics])
        print(f"   • {sub} ({len(topics)} topics): [{topic_names}]")

    # 3. Validate Token
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        print("\n" + "!" * 60)
        print("⚠️  MISSING TELEGRAM BOT TOKEN!")
        print("Please set your TELEGRAM_BOT_TOKEN in the .env file:")
        print("   1. Open @BotFather on Telegram")
        print("   2. Send /newbot to create your bot and get the HTTP API Token")
        print("   3. Paste your token in .env as: TELEGRAM_BOT_TOKEN=123456:ABC-DEF...")
        print("   4. Re-run: python run.py")
        print("!" * 60 + "\n")
        sys.exit(1)

    # 4. Build Telegram Application with resilient network timeouts
    request = HTTPXRequest(
        connection_pool_size=10,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0
    )
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .build()
    )

    # 5. Register Handlers
    # Commands
    application.add_handler(CommandHandler("start", handle_dm_start, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("start", start_quiz_command, filters=filters.ChatType.GROUPS))
    application.add_handler(CommandHandler("quiz", start_quiz_command))
    application.add_handler(CommandHandler("dailyquiz", daily_quiz_command))
    application.add_handler(CommandHandler("daily", daily_quiz_command))
    application.add_handler(CommandHandler("daily_quiz", daily_quiz_command))
    application.add_handler(CommandHandler("stopquiz", stop_quiz_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("mystats", mystats_command))
    application.add_handler(CommandHandler("help", help_command))

    # DM Dashboard Navigation Callbacks
    application.add_handler(CallbackQueryHandler(handle_menu_main_callback, pattern=r"^menu_main$"))
    application.add_handler(CallbackQueryHandler(handle_menu_solo_quiz_callback, pattern=r"^menu_solo_quiz$"))
    application.add_handler(CallbackQueryHandler(handle_menu_daily_quiz_callback, pattern=r"^menu_daily_quiz$"))
    application.add_handler(CallbackQueryHandler(handle_menu_leaderboard_callback, pattern=r"^menu_leaderboard$"))
    application.add_handler(CallbackQueryHandler(handle_lb_solo_callback, pattern=r"^lb_solo$"))
    application.add_handler(CallbackQueryHandler(handle_lb_tourn_callback, pattern=r"^lb_tourn$"))
    application.add_handler(CallbackQueryHandler(handle_menu_my_profile_callback, pattern=r"^menu_my_profile$"))
    application.add_handler(CallbackQueryHandler(handle_menu_help_callback, pattern=r"^menu_help$"))

    # Subject & Topic Selection & Replay Callbacks
    application.add_handler(CallbackQueryHandler(handle_subject_callback, pattern=r"^sub:\d+$"))
    application.add_handler(CallbackQueryHandler(handle_topic_callback, pattern=r"^top:\d+:\d+$"))
    application.add_handler(CallbackQueryHandler(handle_back_subjects_callback, pattern=r"^back_subjects$"))
    application.add_handler(CallbackQueryHandler(handle_cancel_callback, pattern=r"^cancel_quiz$"))
    application.add_handler(CallbackQueryHandler(handle_replay_callback, pattern=r"^replay:.+"))

    # Live Poll Answer Handler
    application.add_handler(PollAnswerHandler(handle_poll_answer))

    print("\n🤖 Bot is running! Press Ctrl+C to terminate.")
    application.run_polling()


if __name__ == "__main__":
    main()
