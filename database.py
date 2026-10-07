import os
import sqlite3

DB_NAME = os.path.join('static', 'database.db')


def get_db():
  os.makedirs('static', exist_ok=True)
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  conn = get_db()
  cursor = conn.cursor()

  # Users table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

  # Posts table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT,
            media_filename TEXT,
            media_type TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

  # Storage files table
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

  conn.commit()
  conn.close()
  print('Database and tables initialized successfully!')


if __name__ == '__main__':
  init_db()
