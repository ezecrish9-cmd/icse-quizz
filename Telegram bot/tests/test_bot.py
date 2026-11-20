import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import QUIZZES_DIR, DATABASE_PATH
from src.database import (
    init_db,
    record_round_results,
    record_solo_quiz_result,
    get_group_leaderboard,
    get_global_solo_leaderboard,
    get_global_tournament_leaderboard,
    get_user_stats,
)
from src.quiz_manager import quiz_manager
from src.session_manager import session_manager


def test_database():
    print("Testing Database...")
    init_db()
    assert DATABASE_PATH.exists(), "Database file should exist after init_db()"

    test_group_id = -int(time.time())
    uid1 = int(time.time()) * 10 + 1
    uid2 = int(time.time()) * 10 + 2
    uid3 = int(time.time()) * 10 + 3
    round_scores = {
        uid1: {"first_name": "Alice", "username": "alice_test", "points": 5, "correct_count": 5},
        uid2: {"first_name": "Bob", "username": "bob_test", "points": 3, "correct_count": 3},
        uid3: {"first_name": "Charlie", "username": None, "points": 1, "correct_count": 1},
    }

    winner = record_round_results(
        group_id=test_group_id,
        subject="MATHS",
        topic="Commercial Mathematics & Algebra",
        round_scores=round_scores
    )

    assert winner is not None, "Winner should be identified"
    assert winner["winner_id"] == uid1, "Alice should be the winner with 5 points"
    assert winner["score"] == 5

    # Check group leaderboard
    lb = get_group_leaderboard(test_group_id)
    assert len(lb) == 3, f"Expected 3 players, got {len(lb)}"
    assert lb[0]["user_id"] == uid1
    assert lb[0]["points"] == 5
    assert lb[1]["user_id"] == uid2
    assert lb[1]["points"] == 3

    # Check tournament global leaderboard
    tourn_lb = get_global_tournament_leaderboard()
    assert len(tourn_lb) >= 1
    assert any(p["user_id"] == uid1 for p in tourn_lb)

    # Check user stats in group
    alice_stats = get_user_stats(test_group_id, uid1)
    assert alice_stats["group_points"] == 5
    assert alice_stats["group_rank"] == 1
    assert alice_stats["tournament_wins"] >= 1

    print("✅ Database tournament tests passed!")


def test_solo_play_and_global_leaderboard():
    print("Testing Solo Play & Global Leaderboards...")
    init_db()

    solo_uid = int(time.time()) * 20 + 7
    res = record_solo_quiz_result(
        user_id=solo_uid,
        first_name="SoloScholar",
        username="scholar_test",
        subject="PHYSICS",
        topic="Mechanics, Work & Energy",
        score=4,
        total_questions=5
    )

    assert res["score"] == 4
    assert res["total_questions"] == 5
    assert res["solo_points"] >= 4
    assert res["solo_quizzes_played"] >= 1
    assert res["solo_rank"] >= 1

    # Check Global Solo Leaderboard
    solo_lb = get_global_solo_leaderboard(limit=10)
    assert len(solo_lb) >= 1
    assert any(p["user_id"] == solo_uid for p in solo_lb)

    # Check student profile in DM (group_id=None)
    stats = get_user_stats(None, solo_uid)
    assert stats is not None
    assert stats["first_name"] == "SoloScholar"
    assert stats["solo_points"] >= 4
    assert stats["solo_played"] >= 1
    assert stats["solo_rank"] >= 1
    assert stats["group_rank"] == "-"

    print("✅ Solo play & Global Leaderboard tests passed!")


def test_quiz_manager():
    print("Testing QuizManager...")
    subjects = quiz_manager.get_subjects()
    print(f"Loaded subjects: {subjects}")
    expected_subjects = [
        "BIOLOGY", "CHEMISTRY", "COMPUTER", "ENGLISH 1", "ENGLISH 2",
        "GEOGRAPHY", "HISTORY", "MATHS", "PHYSICS"
    ]
    for s in expected_subjects:
        assert s in subjects, f"Subject {s} should be in catalog"

    eng2_topics = [t["topic"] for t in quiz_manager.get_topics("ENGLISH 2")]
    assert "Julius Caesar" in eng2_topics
    assert "Poetry" in eng2_topics
    assert "Prose" in eng2_topics

    # Test random questions
    questions = quiz_manager.get_random_questions("PHYSICS", "Mechanics, Work & Energy", count=3)
    assert len(questions) == 3
    for q in questions:
        assert "question" in q
        assert "options" in q
        assert "correct_option_id" in q
        assert 0 <= q["correct_option_id"] < len(q["options"])
        assert len(q["options"]) >= 2

    # Test daily quiz question pack
    daily_pack = quiz_manager.get_daily_quiz_questions()
    assert len(daily_pack) == 9, f"Daily pack should have 9 questions, got {len(daily_pack)}"
    daily_subjects = [d["subject"] for d in daily_pack]
    for s in expected_subjects:
        assert s in daily_subjects, f"Daily pack should include {s}"

    print("✅ QuizManager tests passed!")


def test_session_manager():
    print("Testing SessionManager...")
    dm_user_id = 888777
    session = session_manager.start_session(
        group_id=dm_user_id,
        starter_id=dm_user_id,
        starter_name="SoloStudent",
        subject="CHEMISTRY",
        topic="Periodic Table & Chemical Bonding",
        questions=[
            {
                "question": "Sample Solo Q?",
                "options": ["A", "B", "C"],
                "correct_option_id": 2,
                "explanation": "C is the right answer."
            }
        ],
        is_solo=True
    )

    assert session.is_active
    assert session.is_solo is True
    assert session.total_questions == 1
    assert session.current_question["correct_option_id"] == 2

    # Register poll
    poll_id = "solo_poll_999"
    session.current_poll_id = poll_id
    session.current_correct_option_id = 2
    session_manager.register_poll(poll_id, dm_user_id)

    # Record correct answer
    is_correct = session_manager.record_answer(
        poll_id=poll_id,
        user_id=dm_user_id,
        first_name="SoloStudent",
        username="solostudent",
        selected_option_id=2
    )
    assert is_correct is True
    assert session.scores[dm_user_id]["points"] == 1

    ended = session_manager.end_session(dm_user_id)
    assert ended is not None
    assert session_manager.get_session(dm_user_id) is None

    print("✅ SessionManager tests passed!")


if __name__ == "__main__":
    test_database()
    test_solo_play_and_global_leaderboard()
    test_quiz_manager()
    test_session_manager()
    print("\n🎉 ALL TESTS (SOLO & GROUP) PASSED SUCCESSFULLY!")
