import asyncio
import logging
from telegram import Update, Poll
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from src.quiz_manager import quiz_manager

logger = logging.getLogger(__name__)


async def daily_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /dailyquiz, /daily, /daily_quiz and inline button clicks.
    Pulls 1 question from each ICSE subject and posts them as untimed quiz polls.
    Works seamlessly in both Groups and Private DM.
    """
    chat = update.effective_chat
    user = update.effective_user
    if not chat:
        return

    # Reload quizzes if needed to ensure latest questions
    daily_pack = quiz_manager.get_daily_quiz_questions()
    if not daily_pack:
        quiz_manager.load_quizzes()
        daily_pack = quiz_manager.get_daily_quiz_questions()

    if not daily_pack:
        await context.bot.send_message(
            chat_id=chat.id,
            text="❌ No quiz questions available at this time. Please check your quiz files."
        )
        return

    initiator_name = user.first_name if user else "Student"

    intro_msg = (
        f"📅 *ICSE 10TH — DAILY QUIZ PACK* 📅\n"
        f"I am designed exclusively for ICSE 10TH.\n"
        f"Initiated by *{initiator_name}*\n\n"
        f"📌 *Today's Syllabus Challenge:*\n"
        f"• 1 Question from each of the *{len(daily_pack)} ICSE subjects*\n"
        f"• ⚡ *Untimed:* Solve whenever you want at your own pace!\n\n"
        f"🚀 *Questions incoming below:* 👇"
    )

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=intro_msg,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error sending daily intro message: {e}")

    sent_count = 0
    for item in daily_pack:
        subject = item["subject"]
        topic = item["topic"]
        q = item["question_data"]

        question_title = f"📚 [{subject}] ({topic})\n{q['question']}"
        if len(question_title) > 300:
            question_title = question_title[:297] + "..."

        try:
            await context.bot.send_poll(
                chat_id=chat.id,
                question=question_title,
                options=q["options"],
                type=Poll.QUIZ,
                correct_option_id=q["correct_option_id"],
                is_anonymous=False,
                open_period=None,  # Untimed!
                explanation=q.get("explanation") or None
            )
            sent_count += 1
            # Sleep 0.8s between polls to respect Telegram rate limits
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.error(f"Error sending daily poll for {subject}: {e}")
            await asyncio.sleep(1.0)

    logger.info(f"Daily quiz pack completed: sent {sent_count}/{len(daily_pack)} questions to chat {chat.id}")
