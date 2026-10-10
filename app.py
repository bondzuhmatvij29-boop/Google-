import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'google_plus_super_secret_key'

app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

def init_db():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                avatar TEXT DEFAULT 'default.png',
                bio TEXT DEFAULT 'Привіт! Я у Google+'
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
        conn.close()
    except Exception as e:
        print(f"Помилка ініціалізації БД: {e}")

init_db()

@app.route('/')
def index():
    try:
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
    except Exception as e:
        return f"Помилка стрічки: {e}", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            error = "Паролі не співпадають!"
        else:
            try:
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", (username, password))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = "Користувач із таким ім'ям вже існує!"
            except Exception as e:
                error = f"Помилка: {e}"
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            conn = sqlite3.connect('database.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user WHERE username = ? AND password = ?", (username, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('index'))
            else:
                error = "Невірний логін або пароль!"
        except Exception as e:
            error = f"Помилка входу: {e}"
    return render_template('login.html', error=error)

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
    media_filename, media_type = None, None
    
    try:
        if media and media.filename != '':
            media_filename = media.filename
            upload_folder = os.path.join('static', 'uploads')
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
    except Exception as e:
        print(f"Помилка створення поста: {e}")
        
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if request.method == 'POST':
            avatar = request.files.get('avatar')
            if avatar and avatar.filename != '':
                avatar_filename = f"user_{session['user_id']}_{avatar.filename}"
                avatar_folder = os.path.join('static', 'avatars')
                os.makedirs(avatar_folder, exist_ok=True)
                avatar.save(os.path.join(avatar_folder, avatar_filename))
                
                cursor.execute("UPDATE user SET avatar = ? WHERE id = ?", (avatar_filename, session['user_id']))
                conn.commit()
                
        cursor.execute("SELECT * FROM user WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        conn.close()
        return render_template('profile.html', user=user)
    except Exception as e:
        return f"Помилка профілю: {e}", 500

@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    error_msg = None
    
    try:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if request.method == 'POST':
            friend_username = request.form.get('username')
            cursor.execute("SELECT * FROM user WHERE username = ? AND id != ?", (friend_username, user_id))
            target_user = cursor.fetchone()
            
            if target_user:
                target_id = target_user['id']
                cursor.execute("SELECT * FROM friendship WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                               (user_id, target_id, target_id, user_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO friendship (user_id, friend_id, status) VALUES (?, ?, 'pending')",
                                   (user_id, target_id))
                    conn.commit()
                else:
                    error_msg = "Запит уже надіслано або ви вже друзі!"
            else:
                error_msg = "Користувача не знайдено!"
                
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
        
        conn.close()
        return render_template('friends.html', incoming_requests=incoming_requests, my_friends=my_friends, error_msg=error_msg)
    except Exception as e:
        return f"Помилка друзів: {e}", 500

@app.route('/accept_friend/<int:sender_id>')
def accept_friend(sender_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE friendship SET status = 'accepted' WHERE user_id = ? AND friend_id = ?",
                       (sender_id, session['user_id']))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('friends'))

@app.route('/reject_friend/<int:sender_id>')
def reject_friend(sender_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM friendship WHERE user_id = ? AND friend_id = ?",
                       (sender_id, session['user_id']))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('friends'))

@app.route('/remove_friend/<int:friend_id>')
def remove_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM friendship WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                       (session['user_id'], friend_id, friend_id, session['user_id']))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('friends'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    
