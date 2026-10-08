import os
import random
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# Налаштування відправки через Gmail SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"     # <--- Впиши сюди свій Gmail
SENDER_PASSWORD = "your_app_password"     # <--- Впиши сюди 16-значний пароль додатка Google

# Тимчасовий словник для збереження кодів відновлення: {email: code}
RESET_CODES = {}

# Функція ініціалізації бази даних (створює таблиці, якщо їх ще немає)
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Таблиця користувачів (додано поле email)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
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

# Головна сторінка (стрічка постів)
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT post.*, user.username 
        FROM post 
        JOIN user ON post.user_id = user.id 
        ORDER BY post.id DESC
    ''')
    posts = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', posts=posts)

# Сторінка реєстрації
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO user (username, password, email) VALUES (?, ?, ?)", 
                           (username, password, email))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username already exists!")
            
    return render_template('register.html')

# Сторінка входу
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

# Вихід з акаунта
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Крок 1: Запит на відновлення пароля (введення email)
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return render_template('forgot_password.html', error="User with this email was not found!")

        # Генерація 6-значного коду
        code = str(random.randint(100000, 999999))
        RESET_CODES[email] = code
        
        # Відправка листа через Gmail SMTP
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            msg['Subject'] = "Google+ Password Reset Code"
            
            body = f"Your verification code for Google+ password reset is: {code}\nDo not share this code with anyone!"
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
            server.quit()
        except Exception as e:
            print(f"SMTP Error: {e}")
            return render_template('forgot_password.html', error="Failed to send email. Check SMTP settings.")
        
        return render_template('verify_code.html', email=email)
    
    return render_template('forgot_password.html')

# Крок 2: Перевірка коду та оновлення пароля
@app.route('/reset-password-verify', methods=['POST'])
def reset_password_verify():
    email = request.form.get('email')
    code = request.form.get('code')
    new_password = request.form.get('new_password')
    
    if email in RESET_CODES and RESET_CODES[email] == code:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE user SET password = ? WHERE email = ?", (new_password, email))
        conn.commit()
        conn.close()
        
        del RESET_CODES[email]
        return redirect(url_for('login'))
    else:
        return render_template('verify_code.html', email=email, error="Invalid or expired code!")

# Створення нового поста
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

# Сторінка профілю (зміна аватарки)
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

# Сторінка друзів та спільнот
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
        cursor.execute("SELECT * FROM user WHERE username = ? AND id != ?", (friend_username, user_id))
        target_user = cursor.fetchone()
        
        if target_user:
            target_id = target_user['id']
            # Перевірка чи вже є зв'язок
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
            
    # Вхідні запити
    cursor.execute('''
        SELECT user.id as sender_id, user.username, user.avatar 
        FROM friendship 
        JOIN user ON friendship.user_id = user.id 
        WHERE friendship.friend_id = ? AND friendship.status = 'pending'
    ''', (user_id,))
    incoming_requests = cursor.fetchall()
    
    # Список друзів
    cursor.execute('''
        SELECT u.id, u.username, u.avatar 
        FROM friendship f 
        JOIN user u ON (f.user_id = u.id OR f.friend_id = u.id) 
        WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted' AND u.id != ?
    ''', (user_id, user_id, user_id))
    my_friends = cursor.fetchall()
    
    conn.close()
    return render_template('friends.html', incoming_requests=incoming_requests, my_friends=my_friends, error_msg=error_msg)

@app.route('/accept_friend/<int:sender_id>')
def accept_friend(sender_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE friendship SET status = 'accepted' WHERE user_id = ? AND friend_id = ?",
                   (sender_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('friends'))

@app.route('/reject_friend/<int:sender_id>')
def reject_friend(sender_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM friendship WHERE user_id = ? AND friend_id = ?",
                   (sender_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('friends'))

@app.route('/remove_friend/<int:friend_id>')
def remove_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM friendship WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                   (uid, friend_id, friend_id, uid))
    conn.commit()
    conn.close()
    return redirect(url_for('friends'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
