import os
import logging
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

# Налаштування логування для сервера
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'google_plus_ultimate_secure_key_2026')

# Безпечні параметри сесій та куків для хостингу
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Змініть на True, якщо використовується виключно суворий HTTPS
app.permanent_session_lifetime = 86400  # Сесія живе 1 день

def get_db_connection():
    """Створює безпечне підключення до бази даних з Row Factory."""
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logging.error(f"Помилка підключення до БД: {e}")
        raise

def init_db():
    """Ініціалізація та створення всіх необхідних таблиць при старті."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Таблиця користувачів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                avatar TEXT DEFAULT 'default.png',
                bio TEXT DEFAULT 'Привіт! Я користувач Google+'
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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
            )
        ''')
        
        # Таблиця дружби (кола / підписки / друзі)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friendship (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                friend_id INTEGER,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE,
                FOREIGN KEY (friend_id) REFERENCES user (id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("База даних успішно ініціалізована.")
    except Exception as e:
        logging.critical(f"Критична помилка ініціалізації БД: {e}")

# Запускаємо створення таблиць одразу при старті модуля
init_db()


@app.route('/')
def index():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Витягуємо пости разом з даними авторів, відсортовані від найновіших
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
    except Exception as e:
        logging.error(f"Помилка на головній сторінці: {e}")
        return "Виникла помилка на сервері. Спробуйте пізніше.", 500


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not password:
            error = "Введіть ім'я користувача та пароль!"
        elif password != confirm_password:
            error = "Паролі не співпадають!"
        else:
            try:
                hashed_password = generate_password_hash(password)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", 
                               (username, hashed_password))
                conn.commit()
                conn.close()
                logging.info(f"Зареєстровано нового користувача: {username}")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = "Користувач із таким ім'ям вже існує!"
            except Exception as e:
                logging.error(f"Помилка реєстрації: {e}")
                error = "Помилка сервера при реєстрації."
                
    return render_template('register.html', error=error)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()
            
            # Перевірка хешу пароля
            if user and check_password_hash(user['password'], password):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session.permanent = True
                logging.info(f"Користувач {username} успішно увійшов у систему.")
                return redirect(url_for('index'))
            else:
                error = "Невірне ім'я користувача або пароль!"
        except Exception as e:
            logging.error(f"Помилка входу: {e}")
            error = "Помилка сервера під час авторизації."
            
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    username = session.get('username')
    session.clear()
    logging.info(f"Користувач {username} вийшов із системи.")
    return redirect(url_for('login'))


@app.route('/add_post', methods=['POST'])
def add_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    content = request.form.get('content', '').strip()
    media = request.files.get('media')
    
    media_filename = None
    media_type = None
    
    try:
        if media and media.filename != '':
            media_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{media.filename}"
            upload_folder = os.path.join('static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            media.save(os.path.join(upload_folder, media_filename))
            
            ext = media_filename.lower().split('.')[-1]
            if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                media_type = 'image'
            elif ext in ['mp4', 'webm', 'ogg', 'mov']:
                media_type = 'video'
            else:
                media_type = 'file'
                
        if content or media_filename:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO post (user_id, content, media_filename, media_
