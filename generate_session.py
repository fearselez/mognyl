"""
Генерує МІНІМАЛЬНИЙ .session файл (тільки auth data),
стискає gzip, кодує в base64. Зберігає у session_base64.txt.
"""

import base64
import gzip
import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SOURCE = "sender_session.session"

if not os.path.exists(SOURCE):
    print(f"Файл {SOURCE} не знайдено!")
    sys.exit(1)

src = sqlite3.connect(SOURCE)

# Мінімальний файл — тільки sessions + version
mini_path = "sender_session_mini.session"
if os.path.exists(mini_path):
    os.remove(mini_path)

dst = sqlite3.connect(mini_path)

essential_tables = ['version', 'sessions']
for table_name in essential_tables:
    create_sql = src.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'").fetchone()
    if create_sql:
        dst.execute(create_sql[0])
        rows = src.execute(f"SELECT * FROM {table_name}").fetchall()
        if rows:
            placeholders = ','.join(['?' for _ in rows[0]])
            dst.executemany(f"INSERT INTO {table_name} VALUES ({placeholders})", rows)

other_tables = ['entities', 'sent_files', 'update_state']
for table_name in other_tables:
    create_sql = src.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'").fetchone()
    if create_sql:
        dst.execute(create_sql[0])

dst.commit()
dst.execute("VACUUM")
dst.commit()
dst.close()
src.close()

# Читаємо, стискаємо, кодуємо
with open(mini_path, "rb") as f:
    raw_data = f.read()

compressed = gzip.compress(raw_data, compresslevel=9)
encoded = base64.b64encode(compressed).decode("ascii")

with open("session_base64.txt", "w") as f:
    f.write(encoded)

print(f"Оригінал:    {os.path.getsize(SOURCE):,} bytes")
print(f"Мінімальний: {len(raw_data):,} bytes")
print(f"Стиснутий:   {len(compressed):,} bytes")
print(f"Base64:      {len(encoded):,} символів (ліміт 32,768)")
print()

if len(encoded) <= 32768:
    print("OK! Вміщається в Railway env var.")
else:
    print("УВАГА: Все ще перевищує ліміт!")

print(f"\nЗбережено у файл: session_base64.txt")

os.remove(mini_path)
