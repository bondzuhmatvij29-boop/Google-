from datetime import datetime
import os
import sqlite3
import traceback
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_google_plus_revival'

UPLOAD_FOLDER = 'static/uploads'
STORAGE_FOLDER = 'static/storage'
AVATAR_FOLDER = 'static/avatars'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['STORAGE_FOLDER'] = STORAGE_FOLDER
app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Ліміт 5 МБ

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STORAGE_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs('templates', exist_ok=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, 'database.db')


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
            password TEXT NOT NULL,
            avatar TEXT DEFAULT 'default.png'
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

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(friend_id) REFERENCES users(id)
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
        SELECT posts.*, users.username, users.avatar FROM posts 
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


@app.route('/profile', methods=['GET', 'POST'])
def profile():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = get_db()
  cursor = conn.cursor()

  if request.method == 'POST':
    file = request.files.get('avatar')
    if file and file.filename != '':
      filename = secure_filename(file.filename)
      filename = f"user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
      filepath = os.path.join(app.config['AVATAR_FOLDER'], filename)
      file.save(filepath)

      cursor.execute(
          'UPDATE users SET avatar = ? WHERE id = ?',
          (filename, session['user_id']),
      )
      conn.commit()

    conn.close()
    return redirect(url_for('profile'))

  cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
  user = cursor.fetchone()
  conn.close()

  return render_template('profile.html', user=user)


@app.route('/friends', methods=['GET', 'POST'])
def friends():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = get_db()
  cursor = conn.cursor()
  error_msg = None

  if request.method == 'POST':
    target_username = request.form.get('username', '').strip()
    if target_username:
      cursor.execute(
          'SELECT id FROM users WHERE username = ?', (target_username,)
      )
      target_user = cursor.fetchone()

      if not target_user:
        error_msg = f"User '{target_username}' not found."
      elif target_user['id'] == session['user_id']:
        error_msg = 'You cannot add yourself as a friend.'
      else:
        target_id = target_user['id']
        cursor.execute(
            'SELECT * FROM friendships WHERE user_id = ? AND friend_id = ?',
            (session['user_id'], target_id),
        )
        already_friends = cursor.fetchone()

        cursor.execute(
            'SELECT * FROM friend_requests WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)',
            (session['user_id'], target_id, target_id, session['user_id']),
        )
        existing_req = cursor.fetchone()

        if already_friends:
          error_msg = 'You are already friends with this user.'
        elif existing_req:
          error_msg = 'Friend request already sent or pending.'
        else:
          cursor.execute(
              'INSERT INTO friend_requests (sender_id, receiver_id) VALUES (?, ?)',
              (session['user_id'], target_id),
          )
          conn.commit()
          return redirect(url_for('friends'))

  cursor.execute(
      """
        SELECT users.id, users.username, users.avatar FROM friendships
        JOIN users ON friendships.friend_id = users.id
        WHERE friendships.user_id = ?
    """,
      (session['user_id'],),
  )
  my_friends = cursor.fetchall()

  cursor.execute(
      """
        SELECT friend_requests.id as req_id, users.id as sender_id, users.username, users.avatar FROM friend_requests
        JOIN users ON friend_requests.sender_id = users.id
        WHERE friend_requests.receiver_id = ?
    """,
      (session['user_id'],),
  )
  incoming_requests = cursor.fetchall()

  conn.close()
  return render_template(
      'friends.html',
      my_friends=my_friends,
      incoming_requests=incoming_requests,
      error_msg=error_msg,
  )


@app.route('/accept_friend/<int:sender_id>')
def accept_friend(sender_id):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      'DELETE FROM friend_requests WHERE sender_id = ? AND receiver_id = ?',
      (sender_id, session['user_id']),
  )
  cursor.execute(
      'INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)',
      (session['user_id'], sender_id),
  )
  cursor.execute(
      'INSERT INTO friendships (user_id, friend_id) VALUES (?, ?)',
      (sender_id, session['user_id']),
  )
  conn.commit()
  conn.close()
  return redirect(url_for('friends'))


@app.route('/reject_friend/<int:sender_id>')
def reject_friend(sender_id):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      'DELETE FROM friend_requests WHERE sender_id = ? AND receiver_id = ?',
      (sender_id, session['user_id']),
  )
  conn.commit()
  conn.close()
  return redirect(url_for('friends'))


@app.route('/remove_friend/<int:friend_id>')
def remove_friend(friend_id):
  if 'user_id' not in session:
    return redirect(url_for('login'))

  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      'DELETE FROM friendships WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)',
      (session['user_id'], friend_id, friend_id, session['user_id']),
  )
  conn.commit()
  conn.close()
  return redirect(url_for('friends'))


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


if __name__ == '__main__':
  app.run(host='0.0.0.0', port=5000, debug=True)
