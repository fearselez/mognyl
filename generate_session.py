"""
Генерує МІНІМАЛЬНИЙ .session файл (тільки auth data),
кодує в base64 для Railway. Зберігає у файл session_base64.txt.
"""

import base64
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SOURCE = "sender_session.session"

if not os.path.exists(SOURCE):
    print(f"Файл {SOURCE} не знайдено!")
    sys.exit(1)

src = sqlite3.connect(SOURCE)

# Створюємо мінімальний файл — тільки sessions + version (без entities/sent_files кешу)
mini_path = "sender_session_mini.session"
if os.path.exists(mini_path):
    os.remove(mini_path)

dst = sqlite3.connect(mini_path)

# Копіюємо тільки необхідні таблиці
essential_tables = ['version', 'sessions']

for table_name in essential_tables:
    create_sql = src.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'").fetchone()
    if create_sql:
        dst.execute(create_sql[0])
        rows = src.execute(f"SELECT * FROM {table_name}").fetchall()
        if rows:
            placeholders = ','.join(['?' for _ in rows[0]])
            dst.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)

# Створюємо порожні таблиці для entities та інших (Telethon очікує їх)
other_tables = ['entities', 'sent_files', 'update_state']
for table_name in other_tables:
    create_sql = src.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'").fetchone()
    if create_sql:
        dst.execute(create_sql[0])  # Тільки структура, без даних

dst.commit()
dst.execute("VACUUM")
dst.commit()
dst.close()
src.close()

mini_size = os.path.getsize(mini_path)
orig_size = os.path.getsize(SOURCE)
print(f"Оригінальний розмір: {orig_size:,} bytes")
print(f"Мінімальний розмір:  {mini_size:,} bytes")

# Кодуємо в base64
with open(mini_path, "rb") as f:
    data = f.read()

encoded = base64.b64encode(data).decode("ascii")

# Зберігаємо у файл
with open("session_base64.txt", "w") as f:
    f.write(encoded)

print(f"Base64 розмір:       {len(encoded):,} символів")
print(f"\nЗбережено у файл: session_base64.txt")
print("Скопіюй вміст цього файлу як SESSION_BASE64 в Railway Variables.")

# Прибираємо тимчасовий файл
os.remove(mini_path)
