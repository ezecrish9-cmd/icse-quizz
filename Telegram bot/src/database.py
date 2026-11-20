import logging
from typing import Optional, List, Dict, Any
from src.config import DATABASE_PATH, DATABASE_URL

logger = logging.getLogger(__name__)


def is_postgres() -> bool:
    return bool(DATABASE_URL)


def get_connection():
    """Return database connection (PostgreSQL for cloud if DATABASE_URL is set, else SQLite)."""
    if is_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def execute_sql(conn, sql: str, params: tuple = ()):
    """Execute SQL query adapting placeholders for SQLite (?) or PostgreSQL (%s)."""
    cursor = conn.cursor()
    if is_postgres():
        sql = sql.replace("?", "%s")
    cursor.execute(sql, params)
    return cursor


def init_db() -> None:
    """Initialize database tables for user stats, group leaderboards, and round history."""
    with get_connection() as conn:
        cursor = conn.cursor()

        if is_postgres():
            logger.info("🐘 Initializing PostgreSQL database (Neon / Cloud)...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    solo_points INTEGER DEFAULT 0,
                    solo_quizzes_played INTEGER DEFAULT 0,
                    tournament_points INTEGER DEFAULT 0,
                    tournament_quizzes_played INTEGER DEFAULT 0,
                    tournament_wins INTEGER DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    quizzes_played INTEGER DEFAULT 0,
                    quizzes_won INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS group_scores (
                    group_id BIGINT,
                    user_id BIGINT,
                    points INTEGER DEFAULT 0,
                    quizzes_played INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );

                CREATE TABLE IF NOT EXISTS round_history (
                    round_id SERIAL PRIMARY KEY,
                    group_id BIGINT,
                    subject TEXT,
                    topic TEXT,
                    winner_user_id BIGINT,
                    winner_score INTEGER,
                    participant_count INTEGER,
                    ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        else:
            logger.info("💾 Initializing local SQLite database...")
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    solo_points INTEGER DEFAULT 0,
                    solo_quizzes_played INTEGER DEFAULT 0,
                    tournament_points INTEGER DEFAULT 0,
                    tournament_quizzes_played INTEGER DEFAULT 0,
                    tournament_wins INTEGER DEFAULT 0,
                    total_points INTEGER DEFAULT 0,
                    quizzes_played INTEGER DEFAULT 0,
                    quizzes_won INTEGER DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS group_scores (
                    group_id INTEGER,
                    user_id INTEGER,
                    points INTEGER DEFAULT 0,
                    quizzes_played INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );

                CREATE TABLE IF NOT EXISTS round_history (
                    round_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    subject TEXT,
                    topic TEXT,
                    winner_user_id INTEGER,
                    winner_score INTEGER,
                    participant_count INTEGER,
                    ended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

        conn.commit()


def upsert_user(user_id: int, first_name: str, username: Optional[str] = None) -> None:
    """Ensure user exists and update display name."""
    with get_connection() as conn:
        execute_sql(conn, """
            INSERT INTO users (user_id, first_name, username, last_seen)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = COALESCE(excluded.username, users.username),
                last_seen = CURRENT_TIMESTAMP
        """, (user_id, first_name, username))
        conn.commit()


def record_solo_quiz_result(
    user_id: int,
    first_name: str,
    username: Optional[str],
    subject: str,
    topic: str,
    score: int,
    total_questions: int
) -> Dict[str, Any]:
    """
    Persist solo quiz score to the database.
    Updates solo points, solo games played, and returns updated rank.
    """
    with get_connection() as conn:
        execute_sql(conn, """
            INSERT INTO users (
                user_id, first_name, username,
                solo_points, solo_quizzes_played,
                total_points, quizzes_played, last_seen
            )
            VALUES (?, ?, ?, ?, 1, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = COALESCE(excluded.username, users.username),
                solo_points = users.solo_points + excluded.solo_points,
                solo_quizzes_played = users.solo_quizzes_played + 1,
                total_points = users.total_points + excluded.solo_points,
                quizzes_played = users.quizzes_played + 1,
                last_seen = CURRENT_TIMESTAMP
        """, (user_id, first_name, username, score, score))

        # Log round history with group_id = 0 (denotes solo play)
        execute_sql(conn, """
            INSERT INTO round_history (group_id, subject, topic, winner_user_id, winner_score, participant_count)
            VALUES (0, ?, ?, ?, ?, 1)
        """, (subject, topic, user_id, score))

        conn.commit()

        # Query updated solo points and rank
        cur = execute_sql(conn, "SELECT solo_points, solo_quizzes_played FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        solo_pts = row["solo_points"] if row else score
        solo_played = row["solo_quizzes_played"] if row else 1

        cur_rank = execute_sql(conn, "SELECT COUNT(*) + 1 AS rank FROM users WHERE solo_points > ?", (solo_pts,))
        rank_row = cur_rank.fetchone()
        solo_rank = rank_row["rank"] if rank_row else 1

        return {
            "score": score,
            "total_questions": total_questions,
            "solo_points": solo_pts,
            "solo_quizzes_played": solo_played,
            "solo_rank": solo_rank
        }


def record_round_results(
    group_id: int,
    subject: str,
    topic: str,
    round_scores: Dict[int, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Persist group tournament round scores to the database.
    Updates tournament stats in users and group_scores, then logs round history.
    """
    if not round_scores:
        return None

    # Sort participants by points descending
    sorted_players = sorted(
        round_scores.items(),
        key=lambda item: item[1].get("points", 0),
        reverse=True
    )

    winner_id, winner_data = sorted_players[0]
    winner_score = winner_data.get("points", 0)

    with get_connection() as conn:
        for user_id, data in sorted_players:
            points = data.get("points", 0)
            first_name = data.get("first_name", "Anonymous")
            username = data.get("username", None)
            is_winner = 1 if (user_id == winner_id and winner_score > 0) else 0

            # 1. Update/Insert in users table
            execute_sql(conn, """
                INSERT INTO users (
                    user_id, first_name, username,
                    tournament_points, tournament_quizzes_played, tournament_wins,
                    total_points, quizzes_played, quizzes_won, last_seen
                )
                VALUES (?, ?, ?, ?, 1, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    first_name = excluded.first_name,
                    username = COALESCE(excluded.username, users.username),
                    tournament_points = users.tournament_points + excluded.tournament_points,
                    tournament_quizzes_played = users.tournament_quizzes_played + 1,
                    tournament_wins = users.tournament_wins + excluded.tournament_wins,
                    total_points = users.total_points + excluded.tournament_points,
                    quizzes_played = users.quizzes_played + 1,
                    quizzes_won = users.quizzes_won + excluded.tournament_wins,
                    last_seen = CURRENT_TIMESTAMP
            """, (user_id, first_name, username, points, is_winner, points, is_winner))

            # 2. Update/Insert in group_scores table
            execute_sql(conn, """
                INSERT INTO group_scores (group_id, user_id, points, quizzes_played, last_active)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(group_id, user_id) DO UPDATE SET
                    points = group_scores.points + excluded.points,
                    quizzes_played = group_scores.quizzes_played + 1,
                    last_active = CURRENT_TIMESTAMP
            """, (group_id, user_id, points))

        # 3. Log round in history
        execute_sql(conn, """
            INSERT INTO round_history (group_id, subject, topic, winner_user_id, winner_score, participant_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            group_id,
            subject,
            topic,
            winner_id if winner_score > 0 else None,
            winner_score,
            len(round_scores)
        ))

        conn.commit()

    return {
        "winner_id": winner_id,
        "first_name": winner_data.get("first_name"),
        "username": winner_data.get("username"),
        "score": winner_score
    }


def get_group_leaderboard(group_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Return top users in a specific group ranked by points."""
    with get_connection() as conn:
        cur = execute_sql(conn, """
            SELECT 
                u.user_id,
                u.first_name,
                u.username,
                g.points,
                g.quizzes_played
            FROM group_scores g
            JOIN users u ON g.user_id = u.user_id
            WHERE g.group_id = ? AND g.points > 0
            ORDER BY g.points DESC, g.quizzes_played ASC
            LIMIT ?
        """, (group_id, limit))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_global_solo_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Return top solo players worldwide ranked by solo points."""
    with get_connection() as conn:
        cur = execute_sql(conn, """
            SELECT 
                user_id,
                first_name,
                username,
                solo_points,
                solo_quizzes_played
            FROM users
            WHERE solo_points > 0
            ORDER BY solo_points DESC, solo_quizzes_played ASC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]


def get_global_tournament_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Return top tournament champions worldwide ranked by wins and points."""
    with get_connection() as conn:
        cur = execute_sql(conn, """
            SELECT 
                user_id,
                first_name,
                username,
                tournament_points,
                tournament_quizzes_played,
                tournament_wins
            FROM users
            WHERE tournament_wins > 0 OR tournament_points > 0
            ORDER BY tournament_wins DESC, tournament_points DESC, tournament_quizzes_played ASC
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]


def get_user_stats(group_id: Optional[int], user_id: int) -> Optional[Dict[str, Any]]:
    """Return full stats for a user across Solo, Tournament, and Group."""
    with get_connection() as conn:
        if group_id and group_id < 0:
            cur = execute_sql(conn, """
                SELECT 
                    u.first_name,
                    u.username,
                    COALESCE(u.solo_points, 0) AS solo_points,
                    COALESCE(u.solo_quizzes_played, 0) AS solo_played,
                    COALESCE(u.tournament_points, 0) AS tournament_points,
                    COALESCE(u.tournament_quizzes_played, 0) AS tournament_played,
                    COALESCE(u.tournament_wins, 0) AS tournament_wins,
                    COALESCE(g.points, 0) AS group_points,
                    COALESCE(g.quizzes_played, 0) AS group_played
                FROM users u
                LEFT JOIN group_scores g ON u.user_id = g.user_id AND g.group_id = ?
                WHERE u.user_id = ?
            """, (group_id, user_id))
        else:
            cur = execute_sql(conn, """
                SELECT 
                    u.first_name,
                    u.username,
                    COALESCE(u.solo_points, 0) AS solo_points,
                    COALESCE(u.solo_quizzes_played, 0) AS solo_played,
                    COALESCE(u.tournament_points, 0) AS tournament_points,
                    COALESCE(u.tournament_quizzes_played, 0) AS tournament_played,
                    COALESCE(u.tournament_wins, 0) AS tournament_wins,
                    0 AS group_points,
                    0 AS group_played
                FROM users u
                WHERE u.user_id = ?
            """, (user_id,))

        row = cur.fetchone()
        if not row:
            return None

        stats = dict(row)

        # Solo Rank
        cur_solo = execute_sql(conn, "SELECT COUNT(*) + 1 AS rank FROM users WHERE solo_points > ?", (stats["solo_points"],))
        solo_rank_row = cur_solo.fetchone()
        stats["solo_rank"] = solo_rank_row["rank"] if solo_rank_row else 1

        # Tournament Rank
        cur_tourn = execute_sql(conn, """
            SELECT COUNT(*) + 1 AS rank FROM users 
            WHERE tournament_wins > ? OR (tournament_wins = ? AND tournament_points > ?)
        """, (stats["tournament_wins"], stats["tournament_wins"], stats["tournament_points"]))
        tourn_rank_row = cur_tourn.fetchone()
        stats["tournament_rank"] = tourn_rank_row["rank"] if tourn_rank_row else 1

        # Group Rank (if in group)
        if group_id and group_id < 0:
            cur_grp = execute_sql(conn, "SELECT COUNT(*) + 1 AS rank FROM group_scores WHERE group_id = ? AND points > ?", (group_id, stats["group_points"]))
            rank_row = cur_grp.fetchone()
            stats["group_rank"] = rank_row["rank"] if rank_row else 1
        else:
            stats["group_rank"] = "-"

        return stats
