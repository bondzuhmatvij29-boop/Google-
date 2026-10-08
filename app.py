import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Таблиця користувачів (без зайвих полів email)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar TEXT DEFAULT 'default.png'
        )
    ''')
    
    # Таблиця постів
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
    
    # Таблиця друзів/запитів
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendship (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            friend_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()


@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
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
            
    conn.close()
    
    return render_template('index.html', posts=posts, current_user_data=current_user_data)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match!")
            
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", 
                           (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username already exists!")
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid username or password!")
            
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
    
    if media and media.filename != '':
        media_filename = media.filename
        upload_folder = 'static/uploads'
        os.makedirs(upload_folder, exist_ok=True)
        media.save(os.path.join(upload_folder, media_filename))
        
        if media_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            media_type = 'image'
        elif media_filename.lower().endswith(('.mp4', '.webm', '.ogg')):
            media_type = 'video'
        else:
            media_type = 'file'
            
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO post (user_id, content, media_filename, media_type) VALUES (?, ?, ?, ?)",
                   (session['user_id'], content, media_filename, media_type))
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if request.method == 'POST':
        avatar = request.files.get('avatar')
        if avatar and avatar.filename != '':
            avatar_filename = f"user_{session['user_id']}_{avatar.filename}"
            avatar_folder = 'static/avatars'
            os.makedirs(avatar_folder, exist_ok=True)
            avatar.save(os.path.join(avatar_folder, avatar_filename))
            
            cursor.execute("UPDATE user SET avatar = ? WHERE id = ?", (avatar_filename, session['user_id']))
            conn.commit()
            
    cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('profile.html', user=user)


@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    error_msg = None
    if request.method == 'POST':
        friend_username = request.form.get('username')
        cursor.execute("SELECT * FROM user WHERE username = ? AND id != ?", (friend_username
