import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUIZZES_DIR = DATA_DIR / "quizzes"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)
QUIZZES_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Quiz Settings
POLL_DURATION_SECONDS = int(os.getenv("POLL_DURATION_SECONDS", "20"))
QUESTIONS_PER_ROUND = int(os.getenv("QUESTIONS_PER_ROUND", "5"))
DELAY_BETWEEN_QUESTIONS = int(os.getenv("DELAY_BETWEEN_QUESTIONS", "3"))

# Database Path
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "quiz_bot.db")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
