from datetime import datetime
import os
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Налаштування бази даних (працюватиме і локально, і на Render)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  author = db.Column(db.String(50), nullable=False)
  content = db.Column(db.Text, nullable=False)
  timestamp = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
  db.create_all()


@app.route('/')
def index():
  posts = Post.query.order_by(Post.timestamp.desc()).all()
  return render_template('index.html', posts=posts)


@app.route('/add', methods=['POST'])
def add_post():
  author = request.form.get('author')
  content = request.form.get('content')

  if author and content:
    new_post = Post(author=author, content=content)
    db.session.add(new_post)
    db.session.commit()

  return redirect(url_for('index'))


if __name__ == '__main__':
  # Цей рядок спрацьовує тільки коли ви запускаєте код локально у себе на ПК
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
