import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.config import QUIZZES_DIR

logger = logging.getLogger(__name__)


class QuizManager:
    """Manages loading, validation, and retrieval of quiz questions from JSON files."""

    def __init__(self, quizzes_dir: Path = QUIZZES_DIR):
        self.quizzes_dir = quizzes_dir
        # Structure: { subject: { topic: { "description": str, "questions": list } } }
        self._catalog: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.load_quizzes()

    def load_quizzes(self) -> None:
        """Scan quizzes_dir recursively and load all valid .json quiz files."""
        self._catalog.clear()
        if not self.quizzes_dir.exists():
            logger.warning(f"Quizzes directory does not exist: {self.quizzes_dir}")
            return

        json_files = list(self.quizzes_dir.rglob("*.json"))
        logger.info(f"Found {len(json_files)} quiz JSON files in {self.quizzes_dir}")

        for filepath in json_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                subject = data.get("subject", "").strip()
                topic = data.get("topic", "").strip()
                description = data.get("description", "").strip()
                raw_questions = data.get("questions", [])

                if not subject or not topic or not raw_questions:
                    logger.warning(f"Skipping {filepath}: Missing subject, topic, or questions.")
                    continue

                valid_questions = []
                for q in raw_questions:
                    question_text = q.get("question", "").strip()
                    options = [str(opt).strip() for opt in q.get("options", []) if str(opt).strip()]
                    correct_id = q.get("correct_option_id")
                    explanation = q.get("explanation", "").strip()

                    # Telegram Poll limitations:
                    # Question length: max 300 chars
                    # Number of options: 2 to 10
                    # Option text length: max 100 chars
                    # Explanation length: max 200 chars
                    if not question_text or len(question_text) > 300:
                        continue
                    if len(options) < 2 or len(options) > 10:
                        continue
                    if any(len(opt) > 100 for opt in options):
                        continue
                    if not isinstance(correct_id, int) or correct_id < 0 or correct_id >= len(options):
                        continue
                    if len(explanation) > 200:
                        explanation = explanation[:197] + "..."

                    valid_questions.append({
                        "question": question_text,
                        "options": options,
                        "correct_option_id": correct_id,
                        "explanation": explanation
                    })

                if not valid_questions:
                    logger.warning(f"No valid questions found in {filepath}")
                    continue

                if subject not in self._catalog:
                    self._catalog[subject] = {}

                self._catalog[subject][topic] = {
                    "description": description,
                    "questions": valid_questions,
                    "filepath": str(filepath)
                }
                logger.info(f"Loaded {len(valid_questions)} questions for '{subject}' -> '{topic}'")

            except Exception as e:
                logger.error(f"Error loading quiz file {filepath}: {e}")

    def get_subjects(self) -> List[str]:
        """Return list of available subjects."""
        return sorted(list(self._catalog.keys()))

    def get_topics(self, subject: str) -> List[Dict[str, Any]]:
        """Return list of topics under a specific subject."""
        if subject not in self._catalog:
            return []
        topics = []
        for topic_name, data in sorted(self._catalog[subject].items()):
            topics.append({
                "topic": topic_name,
                "description": data.get("description", ""),
                "question_count": len(data.get("questions", []))
            })
        return topics

    def get_topic_data(self, subject: str, topic: str) -> Optional[Dict[str, Any]]:
        """Return raw data for a specific subject and topic."""
        return self._catalog.get(subject, {}).get(topic)

    def get_random_questions(self, subject: str, topic: str, count: int = 5) -> List[Dict[str, Any]]:
        """Return a randomized batch of questions for the selected subject and topic."""
        topic_data = self.get_topic_data(subject, topic)
        if not topic_data:
            return []

        questions = topic_data.get("questions", [])
        if not questions:
            return []

        # If available questions are fewer than count, take all shuffled
        sample_count = min(count, len(questions))
        return random.sample(questions, sample_count)

    def get_daily_quiz_questions(self) -> List[Dict[str, Any]]:
        """
        Pull 1 random question from each available subject.
        Returns a list of dicts with subject, topic, and question_data.
        """
        daily_pack = []
        for subject in self.get_subjects():
            topics = self.get_topics(subject)
            if not topics:
                continue
            chosen_topic = random.choice(topics)["topic"]
            questions = self.get_random_questions(subject, chosen_topic, count=1)
            if questions:
                daily_pack.append({
                    "subject": subject,
                    "topic": chosen_topic,
                    "question_data": questions[0]
                })
        return daily_pack


# Global instance
quiz_manager = QuizManager()
