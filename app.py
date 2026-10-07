from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_google_plus'  # Required for session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# User table
class User(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(50), unique=True, nullable=False)
  password = db.Column(db.String(200), nullable=False)


# Post table (linked to user)
class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  content = db.Column(db.Text, nullable=False)
  timestamp = db.Column(db.DateTime, default=datetime.utcnow)

  author = db.relationship('User', backref=db.backref('posts', lazy=True))


with app.app_context():
  db.create_all()


@app.route('/')
def index():
  posts = Post.query.order_by(Post.timestamp.desc()).all()
  return render_template('index.html', posts=posts)


# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')

    user_exists = User.query.filter_by(username=username).first()
    if user_exists:
      flash("This username is already taken!", "error")
      return redirect(url_for('register'))

    hashed_password = generate_password_hash(password, method='scrypt')
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    flash("Account successfully created! Please log in.", "success")
    return redirect(url_for('login'))

  return render_template('register.html')


# Login
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
      flash("Invalid username or password!", "error")

  return render_template('login.html')


# Logout
@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('index'))


# Create post (logged-in users only)
@app.route('/add', methods=['POST'])
def add_post():
  if 'user_id' not in session:
    return redirect(url_for('login'))

  content = request.form.get('content')
  if content:
    new_post = Post(user_id=session['user_id'], content=content)
    db.session.add(new_post)
    db.session.commit()

  return redirect(url_for('index'))


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
