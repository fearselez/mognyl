"""
Генератор StringSession для Telethon.

Запускати ЛОКАЛЬНО один раз, щоб конвертувати файлову сесію
в рядок StringSession для використання на Railway.

Використання:
    python generate_session.py

Після запуску:
    1. Скопіюй рядок StringSession з консолі
    2. Додай його як змінну SESSION_STRING в Railway Dashboard
"""

import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Fix Windows console encoding for emoji
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")


async def main():
    # Підключаємось через існуючу файлову сесію
    file_client = TelegramClient('sender_session', API_ID, API_HASH)
    await file_client.connect()

    if not await file_client.is_user_authorized():
        print("❌ Файлова сесія не авторизована!")
        print("   Спочатку запусти main.py і авторизуйся через GUI.")
        await file_client.disconnect()
        return

    # Отримуємо auth key з файлової сесії
    auth_key = file_client.session.auth_key

    # Створюємо StringSession з тим самим auth key
    string_session = StringSession()
    string_session.set_dc(
        file_client.session.dc_id,
        file_client.session.server_address,
        file_client.session.port
    )
    string_session.auth_key = auth_key

    session_string = string_session.save()

    # Перевіряємо що StringSession працює
    print("\n🔄 Перевірка StringSession...")
    test_client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    await test_client.connect()

    if await test_client.is_user_authorized():
        me = await test_client.get_me()
        print(f"✅ StringSession працює! Авторизований як: {me.first_name} ({me.phone})")
        print("\n" + "=" * 60)
        print("🔑 Твоя StringSession (скопіюй весь рядок нижче):")
        print("=" * 60)
        print(session_string)
        print("=" * 60)
        print("\n⚠️  УВАГА: Цей рядок дає повний доступ до акаунту!")
        print("   Нікому не показуй його. Додай як SESSION_STRING в Railway.")
    else:
        print("❌ StringSession не працює. Спробуй видалити sender_session.session і авторизуватись заново.")

    await test_client.disconnect()
    await file_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
