from datetime import datetime
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Налаштування локальної бази даних SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Модель бази даних для повідомлень (публікацій)
class Post(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  author = db.Column(db.String(50), nullable=False)
  content = db.Column(db.Text, nullable=False)
  timestamp = db.Column(
      db.DateTime, default=datetime.utcnow
  )  # Час публікації


# Створення бази даних перед запуском
with app.app_context():
  db.create_all()


@app.route('/')
def index():
  # Отримуємо всі пости з бази даних, сортуємо від найновіших до найстаріших
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
  # Сервер запущений у режимі debug, щоб було зручно тестувати
  app.run(host='0.0.0.0', port=5000, debug=True)
