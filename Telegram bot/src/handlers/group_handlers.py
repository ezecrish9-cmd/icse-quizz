import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from src.config import POLL_DURATION_SECONDS, QUESTIONS_PER_ROUND, DELAY_BETWEEN_QUESTIONS
from src.quiz_manager import quiz_manager
from src.session_manager import session_manager
from src import database

logger = logging.getLogger(__name__)


async def is_authorized_user(update: Update, context: ContextTypes.DEFAULT_TYPE, starter_id: int) -> bool:
    """Check if the acting user is the starter or a group administrator. Always True in private DM."""
    user = update.effective_user
    chat = update.effective_chat
    if not user:
        return False
    if chat and chat.type == ChatType.PRIVATE:
        return True
    if user.id == starter_id:
        return True

    if not chat:
        return False

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ["creator", "administrator"]:
            return True
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")
    return False


async def start_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered by /quiz or /start. Displays subject selection keyboard (Group or DM)."""
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    is_solo = (chat.type == ChatType.PRIVATE)

    # Check if a quiz is already active in this chat
    active_session = session_manager.get_session(chat.id)
    if active_session and active_session.is_active:
        await update.message.reply_text(
            f"⚠️ A quiz on *{active_session.subject} - {active_session.topic}* is already in progress!\n"
            f"Please wait for it to finish or type /stopquiz to end it.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    subjects = quiz_manager.get_subjects()
    if not subjects:
        await update.message.reply_text(
            "❌ No quizzes are currently available. Please contact the administrator.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Set pending selection for this chat
    session_manager.set_pending_selection(
        group_id=chat.id,
        starter_id=user.id,
        starter_name=user.first_name
    )

    # Build subject keyboard (2 subjects per row)
    keyboard = []
    row = []
    for idx, subject in enumerate(subjects):
        row.append(InlineKeyboardButton(f"📚 {subject}", callback_data=f"sub:{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    cancel_cb = "menu_main" if is_solo else "cancel_quiz"
    cancel_text = "🏠 Main Menu" if is_solo else "❌ Cancel"
    keyboard.append([InlineKeyboardButton(cancel_text, callback_data=cancel_cb)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    starter_display = f"[{user.first_name}](tg://user?id={user.id})"
    title = "🎯 *ICSE 10TH SOLO PRACTICE QUIZ*" if is_solo else "🎯 *ICSE 10TH LIVE QUIZ*"
    mode_desc = "⚡ *Mode:* Instant progression upon answering" if is_solo else f"Initiated by: {starter_display}"

    await update.message.reply_text(
        f"{title}\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"{mode_desc}\n\n"
        f"👉 *Select an ICSE Subject to begin:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_subject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subject selection button click."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    if not chat:
        return

    is_solo = (chat.type == ChatType.PRIVATE)
    pending = session_manager.get_pending_selection(chat.id)
    if not pending:
        if is_solo:
            # If expired in DM, re-initiate selection
            session_manager.set_pending_selection(chat.id, update.effective_user.id, update.effective_user.first_name)
            pending = session_manager.get_pending_selection(chat.id)
        else:
            await query.answer("⚠️ This selection menu has expired. Use /quiz to start a new one.", show_alert=True)
            return

    # Verify authorization
    if not await is_authorized_user(update, context, pending["starter_id"]):
        await query.answer("⚠️ Only the person who initiated this quiz or an admin can select!", show_alert=True)
        return

    data = query.data.split(":")
    if len(data) != 2:
        return

    sub_idx = int(data[1])
    subjects = quiz_manager.get_subjects()
    if sub_idx < 0 or sub_idx >= len(subjects):
        return

    selected_subject = subjects[sub_idx]
    topics = quiz_manager.get_topics(selected_subject)
    if not topics:
        await query.answer("No topics found for this subject.", show_alert=True)
        return

    # Build topic keyboard
    keyboard = []
    for top_idx, t in enumerate(topics):
        btn_text = f"📖 {t['topic']} ({t['question_count']} Qs)"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"top:{sub_idx}:{top_idx}")])

    cancel_cb = "menu_main" if is_solo else "cancel_quiz"
    cancel_text = "🏠 Main Menu" if is_solo else "❌ Cancel"
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Subjects", callback_data="back_subjects"),
        InlineKeyboardButton(cancel_text, callback_data=cancel_cb)
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"📚 *Subject: {selected_subject}*\n\n"
        f"👉 *Select a Topic:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_back_subjects_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back button to return to subject list."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    if not chat:
        return

    is_solo = (chat.type == ChatType.PRIVATE)
    pending = session_manager.get_pending_selection(chat.id)
    if not pending:
        if is_solo:
            session_manager.set_pending_selection(chat.id, update.effective_user.id, update.effective_user.first_name)
            pending = session_manager.get_pending_selection(chat.id)
        else:
            await query.answer("⚠️ This selection menu has expired. Use /quiz to start a new one.", show_alert=True)
            return

    if not await is_authorized_user(update, context, pending["starter_id"]):
        await query.answer("⚠️ Only the person who initiated this quiz or an admin can select!", show_alert=True)
        return

    subjects = quiz_manager.get_subjects()
    keyboard = []
    row = []
    for idx, subject in enumerate(subjects):
        row.append(InlineKeyboardButton(f"📚 {subject}", callback_data=f"sub:{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    cancel_cb = "menu_main" if is_solo else "cancel_quiz"
    cancel_text = "🏠 Main Menu" if is_solo else "❌ Cancel"
    keyboard.append([InlineKeyboardButton(cancel_text, callback_data=cancel_cb)])
    reply_markup = InlineKeyboardMarkup(keyboard)

    starter_display = f"[{pending['starter_name']}](tg://user?id={pending['starter_id']})"
    title = "🎯 *ICSE 10TH SOLO PRACTICE QUIZ*" if is_solo else "🎯 *ICSE 10TH LIVE QUIZ*"
    mode_desc = "⚡ *Mode:* Instant progression upon answering" if is_solo else f"Initiated by: {starter_display}"

    await query.edit_message_text(
        f"{title}\n"
        f"I am designed exclusively for ICSE 10TH.\n\n"
        f"{mode_desc}\n\n"
        f"👉 *Select an ICSE Subject to begin:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def handle_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancelling the quiz selection."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    if not chat:
        return

    pending = session_manager.get_pending_selection(chat.id)
    starter_id = pending["starter_id"] if pending else update.effective_user.id

    if not await is_authorized_user(update, context, starter_id):
        await query.answer("⚠️ Only the person who initiated this quiz or an admin can cancel!", show_alert=True)
        return

    session_manager.clear_pending_selection(chat.id)
    await query.edit_message_text("🚫 *Quiz cancelled.* Type /quiz to start anytime!", parse_mode=ParseMode.MARKDOWN)


async def handle_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle topic selection. Launches the quiz round (Solo or Group)."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    is_solo = (chat.type == ChatType.PRIVATE)
    pending = session_manager.get_pending_selection(chat.id)
    if not pending:
        if is_solo:
            session_manager.set_pending_selection(chat.id, user.id, user.first_name)
            pending = session_manager.get_pending_selection(chat.id)
        else:
            await query.answer("⚠️ This selection menu has expired. Use /quiz to start a new one.", show_alert=True)
            return

    if not await is_authorized_user(update, context, pending["starter_id"]):
        await query.answer("⚠️ Only the person who initiated this quiz or an admin can select!", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    sub_idx = int(parts[1])
    top_idx = int(parts[2])

    subjects = quiz_manager.get_subjects()
    if sub_idx < 0 or sub_idx >= len(subjects):
        return
    subject_name = subjects[sub_idx]

    topics = quiz_manager.get_topics(subject_name)
    if top_idx < 0 or top_idx >= len(topics):
        return
    topic_name = topics[top_idx]["topic"]

    # Fetch randomized questions
    questions = quiz_manager.get_random_questions(
        subject=subject_name,
        topic=topic_name,
        count=QUESTIONS_PER_ROUND
    )

    if not questions:
        await query.answer("No valid questions found for this topic.", show_alert=True)
        return

    # Initialize session
    session = session_manager.start_session(
        group_id=chat.id,
        starter_id=pending["starter_id"],
        starter_name=pending["starter_name"],
        subject=subject_name,
        topic=topic_name,
        questions=questions,
        is_solo=is_solo
    )

    timing_text = "⚡ Instant progression (advances upon answering)" if is_solo else f"{POLL_DURATION_SECONDS}s per question"
    countdown = 3 if is_solo else 5

    await query.edit_message_text(
        f"🚀 *QUIZ READY TO LAUNCH!*\n\n"
        f"📚 *Subject:* {subject_name}\n"
        f"📖 *Topic:* {topic_name}\n"
        f"❓ *Questions:* {len(questions)}\n"
        f"⏱️ *Timer:* {timing_text}\n\n"
        f"🔔 *First question in {countdown} seconds... Get ready!*",
        parse_mode=ParseMode.MARKDOWN
    )

    # Schedule first question
    context.job_queue.run_once(
        send_quiz_question_job,
        when=countdown,
        chat_id=chat.id,
        name=f"quiz_{chat.id}"
    )


async def handle_replay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 1-click replay of a quiz topic."""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    data = query.data.split(":", 2)
    if len(data) != 3:
        return

    subject_name = data[1]
    topic_name = data[2]

    questions = quiz_manager.get_random_questions(
        subject=subject_name,
        topic=topic_name,
        count=QUESTIONS_PER_ROUND
    )

    if not questions:
        await query.answer("Could not load questions for replay.", show_alert=True)
        return

    is_solo = (chat.type == ChatType.PRIVATE)
    session = session_manager.start_session(
        group_id=chat.id,
        starter_id=user.id,
        starter_name=user.first_name,
        subject=subject_name,
        topic=topic_name,
        questions=questions,
        is_solo=is_solo
    )

    timing_text = "⚡ Instant progression" if is_solo else f"{POLL_DURATION_SECONDS}s per question"
    countdown = 3 if is_solo else 5

    await query.message.reply_text(
        f"🚀 *REPLAYING QUIZ!*\n\n"
        f"📚 *Subject:* {subject_name}\n"
        f"📖 *Topic:* {topic_name}\n"
        f"❓ *Questions:* {len(questions)}\n"
        f"⏱️ *Timer:* {timing_text}\n\n"
        f"🔔 *First question in {countdown} seconds...*",
        parse_mode=ParseMode.MARKDOWN
    )

    context.job_queue.run_once(
        send_quiz_question_job,
        when=countdown,
        chat_id=chat.id,
        name=f"quiz_{chat.id}"
    )


async def send_quiz_question_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue worker to send the next quiz question poll."""
    job = context.job
    group_id = job.chat_id

    session = session_manager.get_session(group_id)
    if not session or not session.is_active:
        return

    q = session.current_question
    if not q:
        # No more questions, finalize round
        await finish_quiz_round(group_id, context.bot)
        return

    # Unregister previous poll if present
    if session.current_poll_id:
        session_manager.unregister_poll(session.current_poll_id)

    session.current_correct_option_id = q["correct_option_id"]
    session.current_explanation = q.get("explanation", "")
    session.answered_users_current_q.clear()

    question_title = f"[{session.current_question_index + 1}/{session.total_questions}] {q['question']}"
    if len(question_title) > 300:
        question_title = question_title[:297] + "..."

    is_solo = session.is_solo
    # For solo, 60s fallback so question stays open until user answers
    poll_open_period = 60 if is_solo else POLL_DURATION_SECONDS

    try:
        poll_msg = await context.bot.send_poll(
            chat_id=group_id,
            question=question_title,
            options=q["options"],
            type=Poll.QUIZ,
            correct_option_id=q["correct_option_id"],
            is_anonymous=False,
            open_period=poll_open_period,
            explanation=q.get("explanation") or None
        )

        session.current_poll_id = poll_msg.poll.id
        session.current_message_id = poll_msg.message_id
        session_manager.register_poll(poll_msg.poll.id, group_id)

        # Fallback question transition when poll timer expires
        total_wait = (poll_open_period + 2) if is_solo else (POLL_DURATION_SECONDS + DELAY_BETWEEN_QUESTIONS)
        context.job_queue.run_once(
            question_timeout_job,
            when=total_wait,
            chat_id=group_id,
            name=f"timeout_{group_id}_{session.current_question_index}"
        )
    except Exception as e:
        logger.error(f"Error sending quiz poll to chat {group_id}: {e}")
        await context.bot.send_message(
            chat_id=group_id,
            text=f"⚠️ Failed to send question: {e}. Moving to next question..."
        )
        session.current_question_index += 1
        if session.has_next_question:
            context.job_queue.run_once(send_quiz_question_job, when=2, chat_id=group_id)
        else:
            await finish_quiz_round(group_id, context.bot)


async def question_timeout_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called after poll duration expires or after solo instant advance."""
    group_id = context.job.chat_id
    session = session_manager.get_session(group_id)
    if not session or not session.is_active:
        return

    # Try closing the poll cleanly if still open
    if session.current_message_id:
        try:
            await context.bot.stop_poll(
                chat_id=group_id,
                message_id=session.current_message_id
            )
        except Exception:
            pass  # Already closed by Telegram open_period

    # Move to next question index
    session.current_question_index += 1

    if session.current_question_index < session.total_questions:
        # Schedule next question (1s delay)
        context.job_queue.run_once(
            send_quiz_question_job,
            when=1,
            chat_id=group_id,
            name=f"quiz_{group_id}"
        )
    else:
        # Quiz completed!
        await finish_quiz_round(group_id, context.bot)


async def finish_quiz_round(group_id: int, bot) -> None:
    """Compute results, announce standings, and persist all-time stats (Group or Solo)."""
    session = session_manager.end_session(group_id)
    if not session:
        return

    scores = session.scores
    total_q = session.total_questions

    # 1. Handle Solo DM Finish
    if session.is_solo:
        user_id = session.starter_id
        user_score_data = scores.get(user_id, {})
        pts = user_score_data.get("points", 0)
        pct = int((pts / total_q) * 100) if total_q > 0 else 0

        # Persist solo quiz result in database
        res = database.record_solo_quiz_result(
            user_id=user_id,
            first_name=session.starter_name,
            username=user_score_data.get("username"),
            subject=session.subject,
            topic=session.topic,
            score=pts,
            total_questions=total_q
        )

        if pct == 100:
            badge = "🌟 *PERFECT SCORE! Outstanding ICSE Preparation!* 🌟"
        elif pct >= 80:
            badge = "🎉 *Distinction! Great command over this topic!*"
        elif pct >= 60:
            badge = "👍 *Good effort! Keep practicing to aim for 90%+.*"
        else:
            badge = "📖 *Keep studying! Review your notes and try again.*"

        report_card = (
            f"🎓 *ICSE 10TH SOLO REPORT CARD* 🎓\n"
            f"I am designed exclusively for ICSE 10TH.\n\n"
            f"📚 *Subject:* {session.subject}\n"
            f"📖 *Topic:* {session.topic}\n\n"
            f"📊 *Score:* *{pts}/{total_q}* ({pct}%)\n"
            f"✅ *Correct:* {pts} | ❌ *Incorrect:* {total_q - pts}\n\n"
            f"🏆 *Solo Global Standing:*\n"
            f"• Points Earned: *+{pts} pts*\n"
            f"• Total Solo Points: *{res['solo_points']} pts*\n"
            f"• Worldwide Solo Rank: *#{res['solo_rank']}*\n\n"
            f"{badge}"
        )

        keyboard = [
            [
                InlineKeyboardButton("🔁 Play Again", callback_data=f"replay:{session.subject}:{session.topic}"),
                InlineKeyboardButton("📚 Choose Subject", callback_data="menu_solo_quiz")
            ],
            [
                InlineKeyboardButton("🏆 Global Leaderboard", callback_data="menu_leaderboard"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ]
        ]
        await bot.send_message(
            chat_id=group_id,
            text=report_card,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 2. Handle Group Tournament Finish
    if not scores:
        await bot.send_message(
            chat_id=group_id,
            text=(
                f"🏁 *Quiz Finished!*\n\n"
                f"📚 *{session.subject} — {session.topic}*\n"
                f"Nobody participated or answered this round.\n\n"
                f"Use /quiz anytime to start a new round!"
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Persist in SQLite database
    database.record_round_results(
        group_id=group_id,
        subject=session.subject,
        topic=session.topic,
        round_scores=scores
    )

    # Sort participants by points descending
    sorted_players = sorted(
        scores.items(),
        key=lambda item: item[1].get("points", 0),
        reverse=True
    )

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for rank, (user_id, data) in enumerate(sorted_players):
        pts = data.get("points", 0)
        pct = int((pts / total_q) * 100) if total_q > 0 else 0
        name = data.get("first_name", "Player")
        username = data.get("username")
        display_name = f"@{username}" if username else name

        if rank < len(medals):
            medal = medals[rank]
            lines.append(f"{medal} *{rank + 1}. {display_name}* — {pts}/{total_q} pts ({pct}%)")
        else:
            lines.append(f"▫️ {rank + 1}. {display_name} — {pts}/{total_q} pts ({pct}%)")

    standings_text = "\n".join(lines)

    result_message = (
        f"🏆 *FINAL QUIZ RESULTS* 🏆\n\n"
        f"📚 *Subject:* {session.subject}\n"
        f"📖 *Topic:* {session.topic}\n"
        f"❓ *Total Questions:* {total_q}\n\n"
        f"📊 *Round Standings:*\n"
        f"{standings_text}\n\n"
        f"🎉 Congratulations to our winners!\n"
        f"Check all-time group rankings with /leaderboard\n"
        f"Type /quiz to challenge the group again!"
    )

    await bot.send_message(
        chat_id=group_id,
        text=result_message,
        parse_mode=ParseMode.MARKDOWN
    )
