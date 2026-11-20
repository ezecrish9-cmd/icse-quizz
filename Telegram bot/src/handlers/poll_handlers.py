import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.session_manager import session_manager

logger = logging.getLogger(__name__)


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered whenever a participant answers a live quiz poll (Group or DM)."""
    answer = update.poll_answer
    if not answer or not answer.option_ids:
        return

    poll_id = answer.poll_id
    user = answer.user
    selected_option_id = answer.option_ids[0]

    session = session_manager.get_session_by_poll_id(poll_id)
    if not session or not session.is_active:
        return

    is_correct = session_manager.record_answer(
        poll_id=poll_id,
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
        selected_option_id=selected_option_id
    )

    logger.info(
        f"PollAnswer from {user.first_name} (ID: {user.id}) in chat {session.group_id}: "
        f"option={selected_option_id}, correct={is_correct}, is_solo={session.is_solo}"
    )

    # In solo DM play, advance immediately after 1.5 seconds so user can see explanation
    if session.is_solo and context.job_queue:
        from src.handlers.group_handlers import question_timeout_job

        # Cancel the pending fallback timeout job for this question
        job_name = f"timeout_{session.group_id}_{session.current_question_index}"
        existing_jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in existing_jobs:
            job.schedule_removal()

        # Schedule question transition in 1.5 seconds
        context.job_queue.run_once(
            question_timeout_job,
            when=1.5,
            chat_id=session.group_id,
            name=f"solo_advance_{session.group_id}"
        )
