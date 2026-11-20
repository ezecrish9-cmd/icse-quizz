from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class GroupQuizSession:
    group_id: int
    starter_id: int
    starter_name: str
    subject: str
    topic: str
    questions: List[Dict[str, Any]]
    current_question_index: int = 0
    current_poll_id: Optional[str] = None
    current_message_id: Optional[int] = None
    current_correct_option_id: int = -1
    current_explanation: str = ""
    is_active: bool = True
    is_solo: bool = False
    timeout_job_name: Optional[str] = None
    answered_users_current_q: Set[int] = field(default_factory=set)
    # scores: { user_id: { "first_name": str, "username": str, "points": int, "correct_count": int } }
    scores: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    @property
    def total_questions(self) -> int:
        return len(self.questions)

    @property
    def current_question(self) -> Optional[Dict[str, Any]]:
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    @property
    def has_next_question(self) -> bool:
        return self.current_question_index + 1 < len(self.questions)


class SessionManager:
    """Manages active live quiz sessions across all Telegram groups and DM chats."""

    def __init__(self):
        # group_id (or user_id in DM) -> GroupQuizSession
        self._active_sessions: Dict[int, GroupQuizSession] = {}
        # poll_id -> group_id
        self._poll_to_group: Dict[str, int] = {}
        # transient starters selecting topics: group_id -> { "starter_id": int, "starter_name": str }
        self._pending_selections: Dict[int, Dict[str, Any]] = {}

    def set_pending_selection(self, group_id: int, starter_id: int, starter_name: str) -> None:
        self._pending_selections[group_id] = {
            "starter_id": starter_id,
            "starter_name": starter_name
        }

    def get_pending_selection(self, group_id: int) -> Optional[Dict[str, Any]]:
        return self._pending_selections.get(group_id)

    def clear_pending_selection(self, group_id: int) -> None:
        self._pending_selections.pop(group_id, None)

    def start_session(
        self,
        group_id: int,
        starter_id: int,
        starter_name: str,
        subject: str,
        topic: str,
        questions: List[Dict[str, Any]],
        is_solo: bool = False
    ) -> GroupQuizSession:
        self.clear_pending_selection(group_id)
        session = GroupQuizSession(
            group_id=group_id,
            starter_id=starter_id,
            starter_name=starter_name,
            subject=subject,
            topic=topic,
            questions=questions,
            is_solo=is_solo
        )
        self._active_sessions[group_id] = session
        return session

    def get_session(self, group_id: int) -> Optional[GroupQuizSession]:
        return self._active_sessions.get(group_id)

    def get_session_by_poll_id(self, poll_id: str) -> Optional[GroupQuizSession]:
        group_id = self._poll_to_group.get(poll_id)
        if group_id is not None:
            return self.get_session(group_id)
        return None

    def register_poll(self, poll_id: str, group_id: int) -> None:
        self._poll_to_group[poll_id] = group_id

    def unregister_poll(self, poll_id: str) -> None:
        self._poll_to_group.pop(poll_id, None)

    def end_session(self, group_id: int) -> Optional[GroupQuizSession]:
        self.clear_pending_selection(group_id)
        session = self._active_sessions.pop(group_id, None)
        if session and session.current_poll_id:
            self.unregister_poll(session.current_poll_id)
        return session

    def record_answer(
        self,
        poll_id: str,
        user_id: int,
        first_name: str,
        username: Optional[str],
        selected_option_id: int
    ) -> bool:
        """
        Record user's answer for the current question in the session.
        Returns True if answer is correct.
        """
        session = self.get_session_by_poll_id(poll_id)
        if not session or not session.is_active:
            return False

        # Initialize user score entry if first time participating
        if user_id not in session.scores:
            session.scores[user_id] = {
                "first_name": first_name,
                "username": username,
                "points": 0,
                "correct_count": 0
            }
        else:
            session.scores[user_id]["first_name"] = first_name
            if username:
                session.scores[user_id]["username"] = username

        session.answered_users_current_q.add(user_id)

        # Check correctness
        if selected_option_id == session.current_correct_option_id:
            session.scores[user_id]["points"] += 1
            session.scores[user_id]["correct_count"] += 1
            return True

        return False


# Global instance
session_manager = SessionManager()
