import sqlite3

# Підключаємося до локальної бази даних
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Твій нікнейм у системі (замість 'твій_нік' впиши своє ім'я користувача)
username_to_reset = 'nexus'
new_password = '123'

# Оновлюємо пароль у базі
cursor.execute("UPDATE user SET password = ? WHERE username = ?", (new_password, username_to_reset))
conn.commit()

# Перевіряємо, чи пройшло оновлення
if cursor.rowcount > 0:
    print(f"✅ Успіх! Пароль для користувача '{username_to_reset}' змінено на '{new_password}'.")
else:
    print(f"⚠️ Користувача з ім'ям '{username_to_reset}' не знайдено.")
    # Виведемо список усіх наявних користувачів, щоб ти міг побачити свій нік
    cursor.execute("SELECT username FROM user")
    users = cursor.fetchall()
    print("Список усіх користувачів у базі:", [u[0] for u in users])

conn.close()
