import sqlite3
import bcrypt
from contextlib import contextmanager

class Database:
    def __init__(self, db_path='boggle.db'):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS player_stats (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    games_played INTEGER DEFAULT 0,
                    games_won INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    total_words INTEGER DEFAULT 0,
                    best_score INTEGER DEFAULT 0,
                    rating INTEGER DEFAULT 1200,
                    rank TEXT DEFAULT 'Школьник',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS game_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ended_at DATETIME,
                    duration INTEGER,
                    winner_id INTEGER REFERENCES users(id)
                );
                
                CREATE TABLE IF NOT EXISTS game_players (
                    game_id INTEGER REFERENCES game_history(id),
                    user_id INTEGER REFERENCES users(id),
                    score INTEGER DEFAULT 0,
                    words_count INTEGER DEFAULT 0,
                    rating_change INTEGER DEFAULT 0,
                    PRIMARY KEY (game_id, user_id)
                );
                
                CREATE TABLE IF NOT EXISTS word_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER REFERENCES game_history(id),
                    user_id INTEGER REFERENCES users(id),
                    word TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    found_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_game_players_user ON game_players(user_id);
                CREATE INDEX IF NOT EXISTS idx_word_history_game ON word_history(game_id);
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            ''')
            print("✅ База данных инициализирована")

    def create_user(self, username, password):
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            user_id = cursor.lastrowid
            cursor.execute(
                'INSERT INTO player_stats (user_id) VALUES (?)',
                (user_id,)
            )
            return user_id

    def get_user(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM users WHERE username = ?',
                (username,)
            )
            return cursor.fetchone()

    def get_user_by_id(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM users WHERE id = ?',
                (user_id,)
            )
            return cursor.fetchone()

    def verify_user(self, username, password):
        user = self.get_user(username)
        if not user:
            return None
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            return user['id']
        return None

    def get_stats(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM player_stats WHERE user_id = ?',
                (user_id,)
            )
            return cursor.fetchone()

    def get_rating(self, user_id):
        stats = self.get_stats(user_id)
        return stats['rating'] if stats else 1200

    def _get_rank_by_rating(self, rating):
        if rating >= 2400:
            return 'Мутант'
        elif rating >= 2100:
            return 'Псих'
        elif rating >= 1800:
            return 'Задрот'
        elif rating >= 1500:
            return 'Умник'
        elif rating >= 1200:
            return 'Школьник'
        elif rating >= 900:
            return 'Карапуз'
        else:
            return 'Амёба'

    def calculate_rating_change(self, player_rating, opponent_rating, player_score, opponent_score):
        import math
        expected = 1 / (1 + math.pow(10, (opponent_rating - player_rating) / 400))
        if player_score > opponent_score:
            actual = 1.0
        elif player_score == opponent_score:
            actual = 0.5
        else:
            actual = 0.0
        k_factor = 32
        return int(k_factor * (actual - expected))

    def save_game_with_rating(self, room_id, players_data, words_data, winner_id, duration=60):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            ratings_before = {}
            for player in players_data:
                cursor.execute(
                    'SELECT rating FROM player_stats WHERE user_id = ?',
                    (player['user_id'],)
                )
                row = cursor.fetchone()
                ratings_before[player['user_id']] = row['rating'] if row else 1200
            
            cursor.execute('''
                INSERT INTO game_history (room_id, ended_at, duration, winner_id)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?)
            ''', (room_id, duration, winner_id))
            game_id = cursor.lastrowid
            
            for player in players_data:
                cursor.execute('''
                    INSERT INTO game_players (game_id, user_id, score, words_count)
                    VALUES (?, ?, ?, ?)
                ''', (game_id, player['user_id'], player['score'], len(player['words'])))
            
            for word in words_data:
                cursor.execute('''
                    INSERT INTO word_history (game_id, user_id, word, points)
                    VALUES (?, ?, ?, ?)
                ''', (game_id, word['user_id'], word['word'], word['points']))
            
            for player in players_data:
                user_id = player['user_id']
                player_score = player['score']
                is_winner = (user_id == winner_id)
                
                opponent_id = None
                opponent_score = None
                for p in players_data:
                    if p['user_id'] != user_id:
                        opponent_id = p['user_id']
                        opponent_score = p['score']
                        break
                
                if opponent_id:
                    rating_change = self.calculate_rating_change(
                        ratings_before[user_id],
                        ratings_before[opponent_id],
                        player_score,
                        opponent_score
                    )
                else:
                    rating_change = 0
                
                cursor.execute(
                    'UPDATE game_players SET rating_change = ? WHERE game_id = ? AND user_id = ?',
                    (rating_change, game_id, user_id)
                )
                
                cursor.execute(
                    'UPDATE player_stats SET rating = rating + ? WHERE user_id = ?',
                    (rating_change, user_id)
                )
                
                cursor.execute('SELECT rating FROM player_stats WHERE user_id = ?', (user_id,))
                new_rating = cursor.fetchone()['rating']
                rank = self._get_rank_by_rating(new_rating)
                cursor.execute(
                    'UPDATE player_stats SET rank = ? WHERE user_id = ?',
                    (rank, user_id)
                )
                
                cursor.execute(
                    'SELECT best_score FROM player_stats WHERE user_id = ?',
                    (user_id,)
                )
                current = cursor.fetchone()
                best_score = max(current['best_score'] if current else 0, player_score)
                
                cursor.execute('''
                    UPDATE player_stats 
                    SET games_played = games_played + 1,
                        total_score = total_score + ?,
                        total_words = total_words + ?,
                        games_won = games_won + ?,
                        best_score = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (player_score, len(player['words']), 1 if is_winner else 0, best_score, user_id))
            
            return game_id

    def get_leaderboard(self, limit=10):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    u.id,
                    u.username,
                    s.games_played,
                    s.games_won,
                    s.total_score,
                    s.total_words,
                    s.best_score,
                    s.rating,
                    s.rank,
                    ROUND(s.total_score / NULLIF(s.games_played, 0), 1) as avg_score
                FROM users u
                JOIN player_stats s ON u.id = s.user_id
                WHERE u.is_active = 1
                ORDER BY s.rating DESC
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()

    def get_user_history(self, user_id, limit=20):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    gh.id,
                    gh.room_id,
                    gh.started_at,
                    gh.ended_at,
                    gp.score,
                    gp.words_count,
                    gp.rating_change,
                    gh.winner_id = ? as is_winner
                FROM game_history gh
                JOIN game_players gp ON gh.id = gp.game_id
                WHERE gp.user_id = ?
                ORDER BY gh.started_at DESC
                LIMIT ?
            ''', (user_id, user_id, limit))
            return cursor.fetchall()
