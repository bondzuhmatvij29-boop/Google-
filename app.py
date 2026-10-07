from datetime import datetime
import os
import sqlite3
import traceback
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_google_plus_revival'

UPLOAD_FOLDER = 'static/uploads'
STORAGE_FOLDER = 'static/storage'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STORAGE_FOLDER'] = STORAGE_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STORAGE_FOLDER, exist_ok=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, 'database.db')


# ГЛОБАЛЬНИЙ ПЕРЕХОПЛЮВАЧ ПОМИЛОК: замість 500 покажемо текст помилки на екрані!
@app.errorhandler(Exception)
def handle_exception(e):
  tb = traceback.format_exc()
  return (
      f'<h2>CRITICAL SERVER ERROR (500):</h2><pre>{tb}</pre>',
      500,
  )


def get_db():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
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


init_db()


@app.route('/')
def index():
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute("""
        SELECT posts.*, users.username FROM posts 
        JOIN users ON posts.user_id = users.id 
        ORDER BY posts.id DESC
    """)
  posts = cursor.fetchall()

  cursor.execute("""
        SELECT storage_files.*, users.username FROM storage_files 
        JOIN users ON storage_files.user_id = users.id 
        ORDER BY storage_files.id DESC
    """)
  storage_files = cursor.fetchall()
  conn.close()
  return render_template(
      'index.html', posts=posts, storage_files=storage_files
  )


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
      return redirect(url_for('register'))

    hashed_password = generate_password_hash(password)
    conn = get_db()
    cursor = conn.cursor()
    try:
      cursor.execute(
          'INSERT INTO users (username, password) VALUES (?, ?)',
          (username, hashed_password),
      )
      conn.commit()
    except sqlite3.IntegrityError:
      conn.close()
      return redirect(url_for('register'))
    conn.close()
    return redirect(url_for('login'))
  return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
      session['user_id'] = user['id']
      session['username'] = user['username']
      return redirect(url_for('index'))
  return render_template('login.html')


@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('index'))


@app.route('/add', methods=['POST'])
def add_post():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  content = request.form.get('content')
  file = request.files.get('media')
  media_filename = None
  media_type = None

  if file and file.filename != '':
    filename = secure_filename(file.filename)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    media_filename = filename

    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
      media_type = 'image'
    elif ext in {'mp4', 'webm', 'ogg', 'mov'}:
      media_type = 'video'
    else:
      media_type = 'file'

  if (content and content.strip() != '') or media_filename:
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO posts (user_id, content, media_filename, media_type, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """,
        (
            session['user_id'],
            content if content else '',
            media_filename,
            media_type,
            timestamp,
        ),
    )
    conn.commit()
    conn.close()

  return redirect(url_for('index'))


@app.route('/upload_file', methods=['POST'])
def upload_file():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  file = request.files.get('storage_file')
  if file and file.filename != '':
    original_name = file.filename
    filename = secure_filename(original_name)
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file.save(os.path.join(app.config['STORAGE_FOLDER'], filename))

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
            INSERT INTO storage_files (user_id, filename, original_filename, timestamp) 
            VALUES (?, ?, ?, ?)
        """,
        (session['user_id'], filename, original_name, timestamp),
    )
    conn.commit()
    conn.close()

  return redirect(url_for('index'))


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
