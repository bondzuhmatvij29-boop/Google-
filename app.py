from datetime import datetime
import os
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_google_plus'

# Папки для завантаження файлів
UPLOAD_FOLDER = 'static/uploads'
MUSIC_FOLDER = 'static/music'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MUSIC_FOLDER'] = MUSIC_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Створюємо папки, якщо їх немає
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MUSIC_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

ALLOWED_IMAGE_VIDEO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'ogg'}
ALLOWED_MUSIC_EXTENSIONS = {'mp3', 'wma', 'aac', 'wav', 'm4a'}


def allowed_file(filename, allowed_set):
  return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


# Таблиця користувачів
class User(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(50), unique=True, nullable=False)
  password = db.Column(db.String(200), nullable=False)


# Таблиця публікацій (з підтримкою медіа)
class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  content = db.Column(db.Text, nullable=True)
  media_filename = db.Column(db.String(200), nullable=True)
  media_type = db.Column(
      db.String(20), nullable=True
  )  # 'image' або 'video'
  timestamp = db.Column(db.DateTime, default=datetime.utcnow)

  author = db.relationship('User', backref=db.backref('posts', lazy=True))


# Таблиця музики для бокової панелі
class Music(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  filename = db.Column(db.String(200), nullable=False)
  original_filename = db.Column(db.String(200), nullable=False)
  timestamp = db.Column(db.DateTime, default=datetime.utcnow)

  uploader = db.relationship('User', backref=db.backref('music', lazy=True))


with app.app_context():
  db.create_all()


@app.route('/')
def index():
  posts = Post.query.order_by(Post.timestamp.desc()).all()
  music_tracks = Music.query.order_by(Music.timestamp.desc()).all()
  return render_template(
      'index.html', posts=posts, music_tracks=music_tracks
  )


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')

    if User.query.filter_by(username=username).first():
      flash('This username is already taken!', 'error')
      return redirect(url_for('register'))

    hashed_password = generate_password_hash(password, method='scrypt')
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    flash('Account successfully created! Please log in.', 'success')
    return redirect(url_for('login'))

  return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
      session['user_id'] = user.id
      session['username'] = user.username
      return redirect(url_for('index'))
    else:
      flash('Invalid username or password!', 'error')

  return render_template('login.html')


@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('index'))


# Створення поста з медіа
@app.route('/add', methods=['POST'])
def add_post():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  content = request.form.get('content')
  file = request.files.get('media')
  media_filename = None
  media_type = None

  if file and file.filename != '':
    if allowed_file(file.filename, ALLOWED_IMAGE_VIDEO_EXTENSIONS):
      filename = secure_filename(file.filename)
      # Додаємо префікс часу, щоб уникнути однакових назв файлів
      filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
      file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
      media_filename = filename

      ext = filename.rsplit('.', 1)[1].lower()
      if ext in {'png', 'jpg', 'jpeg', 'gif'}:
        media_type = 'image'
      elif ext in {'mp4', 'webm', 'ogg'}:
        media_type = 'video'

  if content or media_filename:
    new_post = Post(
        user_id=session['user_id'],
        content=content,
        media_filename=media_filename,
        media_type=media_type,
    )
    db.session.add(new_post)
    db.session.commit()

  return redirect(url_for('index'))


# Завантаження музики в бокову панель
@app.route('/upload_music', methods=['POST'])
def upload_music():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  file = request.files.get('music_file')
  if file and file.filename != '':
    if allowed_file(file.filename, ALLOWED_MUSIC_EXTENSIONS):
      original_name = file.filename
      filename = secure_filename(original_name)
      filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
      file.save(os.path.join(app.config['MUSIC_FOLDER'], filename))

      new_track = Music(
          user_id=session['user_id'],
          filename=filename,
          original_filename=original_name,
      )
      db.session.add(new_track)
      db.session.commit()
    else:
      flash(
          'Invalid audio format! Allowed: MP3, WMA, AAC, WAV, M4A', 'error'
      )

  return redirect(url_for('index'))


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
