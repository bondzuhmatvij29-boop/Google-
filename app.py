import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Безпечне підключення до бази даних
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Гарантована ініціалізація бази даних при старті
def init_db():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    avatar TEXT DEFAULT 'default.png'
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    content TEXT,
                    media_filename TEXT,
                    media_type TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friendship (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    friend_id INTEGER,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            conn.commit()
    except Exception as e:
        print(f"Помилка ініціалізації БД: {e}")

# Викликаємо ініціалізацію одразу
init_db()


@app.route('/')
def index():
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT post.*, user.username, user.avatar 
                FROM post 
                JOIN user ON post.user_id = user.id 
                ORDER BY post.id DESC
            ''')
            posts = cursor.fetchall()
            
            current_user_data = None
            if 'user_id' in session:
                cursor.execute("SELECT id, username, avatar FROM user WHERE id = ?", (session['user_id'],))
                row = cursor.fetchone()
                if row:
                    current_user_data = dict(row)
        
        return render_template('index.html', posts=posts, current_user_data=current_user_data)
    except Exception as e:
        print(f"Помилка на головній: {e}")
        return "Виникла помилка завантаження стрічки. Спробуйте оновити сторінку.", 500


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match!")
            
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="Username already exists!")
        except Exception as e:
            return render_template('register.html', error=f"Помилка реєстрації: {e}")
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user WHERE username = ? AND password = ?", (username, password))
                user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Invalid username or password!")
        except Exception as e:
            return render_template('login.html', error="Помилка сервера при вході.")
            
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/add_post', methods=['POST'])
def add_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    content = request.form.get('content')
    media = request.files.get('media')
    
    media_filename = None
    media_type = None
    
    try:
        if media and media.filename != '':
            media_filename = media.filename
            upload_folder = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            media.save(os.path.join(upload_folder, media_filename))
            
            if media_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                media_type = 'image'
            elif media_filename.lower().endswith(('.mp4', '.webm', '.ogg')):
                media_type = 'video'
            else:
                media_type = 'file'
                
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO post (user_id, content, media_filename, media_type) VALUES (?, ?, ?, ?)",
                           (session['user_id'], content, media_filename, media_type))
            conn.commit()
    except Exception as e:
        print(f"Помилка додавання поста: {e}")
        
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if request.method == 'POST':
                avatar = request.files.get('avatar')
                if avatar and avatar.filename != '':
                    avatar_filename = f"user_{session['user_id']}_{avatar.filename}"
                    avatar_folder = os.path.join(app.root_path, 'static', 'avatars')
                    os.makedirs(avatar_folder, exist_ok=True)
                    avatar.save(os.path.join(avatar_folder, avatar_filename))
                    
                    cursor.execute("UPDATE user SET avatar = ? WHERE id = ?", (avatar_filename, session['user_id']))
                    conn.commit()
                    
            cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
            user = cursor.fetchone()
            
        return render_template('profile.html', user=user)
    except Exception as e:
        print(f"Помилка профілю: {e}")
        return redirect(url_for('index'))


@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    error_msg = None
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if request.method == 'POST':
                friend_username = request.form.get('username')
                cursor.execute("SELECT * FROM user WHERE username = ? AND id != ?", (friend_username, user_id))
                target_user = cursor.fetchone()
                
                if target_user:
                    target_id = target_user['id']
                    cursor.execute("SELECT * FROM friendship WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                                   (user_id, target_id, target_id, user_id))
                    existing = cursor.fetchone()
                    if not existing:
                        cursor.execute("INSERT INTO friendship (user_id, friend_id, status) VALUES (?, ?, 'pending')",
                                       (user_id, target_id))
                        conn.commit()
                    else:
                        error_msg = "Request already sent or you are already friends!"
                else:
                    error_msg = "User not found!"
                    
            cursor.execute('''
                SELECT user.id as sender_id, user.username, user.avatar 
                FROM friendship 
                JOIN user ON friendship.user_id = user.id 
                WHERE friendship.friend_id = ? AND friendship.status = 'pending'
            ''', (user_id,))
            incoming_requests = cursor.fetchall()
            
            cursor.execute('''
                SELECT u.id, u.username, u.avatar 
                FROM friendship f 
                JOIN user u ON (f.user_id = u.id OR f.friend_id = u.id) 
                WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted' AND u.id != ?
            ''', (user_id, user_id, user_id))
            my_friends = cursor.fetchall()
            
        return render_template('friends.html', incoming_requests=incoming_requests, my_friends=my_friends, error
