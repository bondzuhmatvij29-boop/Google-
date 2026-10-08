import os
import random
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

# ==================== НАЛАШТУВАННЯ GMAIL SMTP ====================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"         # <--- Твоя пошта
SENDER_PASSWORD = "your_app_password"         # <--- Пароль додатка (App Password)
# =================================================================

RESET_CODES = {}

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            avatar TEXT DEFAULT 'default.png'
        )
    ''')
    
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN email TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    
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
        cursor.execute("SELECT id, username, email, avatar FROM user WHERE id = ?", (session['user_id'],))
        row = cursor.fetchone()
        if row:
            current_user_data = dict(row)
            
    conn.close()
    
    # Використовуємо твій стандартний файл дизайну index.html
    return render_template('index.html', posts=posts, current_user_data=current_user_data)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match!")
            
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

        code = str(random.randint(100000, 999999))
        RESET_CODES[email] = code
        
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
            return render_template('forgot_password.html', error="Failed to send email. Check SMTP settings or App Password.")
        
        return render_template('verify_code.html', email=email)
    
    return render_template('forgot_password.html')


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
