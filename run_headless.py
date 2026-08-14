"""
Headless Telegram Sender для Railway.

Працює без GUI — читає config.json, підключається через сесію з base64,
запускає розсилку в нескінченному циклі.

Env vars (задаються в Railway Dashboard):
    API_ID          — Telegram API ID
    API_HASH        — Telegram API Hash
    SESSION_BASE64  — Base64 рядок файлу сесії (з generate_session.py)
"""

import asyncio
import base64
import json
import os
import random
import sys
import signal
from datetime import datetime

from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_BASE64 = os.getenv("SESSION_BASE64")

SESSION_FILE = "sender_session"


def log(text: str):
    """Логування з timestamp в stdout (Railway збирає автоматично)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {text}", flush=True)


def restore_session():
    """Відновити .session файл з base64 env var."""
    if not SESSION_BASE64:
        log("SESSION_BASE64 не задано!")
        log("   Запусти generate_session.py локально і додай результат в Railway Variables.")
        sys.exit(1)

    session_path = f"{SESSION_FILE}.session"
    data = base64.b64decode(SESSION_BASE64)
    with open(session_path, "wb") as f:
        f.write(data)
    log(f"Session file restored ({len(data)} bytes)")


def load_config(path: str = "config.json") -> list:
    """Завантажити цілі розсилки з config.json."""
    if not os.path.exists(path):
        log(f"Файл {path} не знайдено!")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    targets = data.get("targets", [])
    if not targets:
        log("config.json порожній — немає груп для розсилки!")
        sys.exit(1)

    return targets


async def group_sender_loop(client: TelegramClient, target_data: dict, send_lock: asyncio.Lock, stop_event: asyncio.Event):
    """Цикл розсилки для однієї групи (та сама логіка що й в telegram_client.py)."""
    group_str = target_data.get("group", "").strip()
    message = target_data.get("message", "").strip()
    delay_min = target_data.get("delay_min", 60)
    delay_max = target_data.get("delay_max", 180)

    if not group_str or not message:
        return

    try:
        target = int(group_str)
    except ValueError:
        target = group_str

    while not stop_event.is_set():
        # Відправка з глобальним локом (уникаємо одночасної відправки)
        async with send_lock:
            if stop_event.is_set():
                break
            log(f"Sending to {group_str}...")
            try:
                entity = await client.get_entity(target)
                await client.send_message(entity, message)
                log(f"OK - sent to {group_str}")
            except Exception as e:
                log(f"ERROR {group_str}: {str(e)}")

            # Мікро-пауза після кожної відправки
            await asyncio.sleep(1.5)

        if stop_event.is_set():
            break

        delay = random.randint(delay_min, delay_max)
        log(f"Waiting {delay}s for {group_str}...")

        # Пауза з кроком 1 сек для швидкого переривання
        for _ in range(delay):
            if stop_event.is_set():
                break
            await asyncio.sleep(1)


async def main():
    # Відновити session файл з base64
    restore_session()

    # Підключення через файлову сесію
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        log("Session invalid! Re-generate via generate_session.py")
        sys.exit(1)

    me = await client.get_me()
    log(f"✅ Підключено як: {me.first_name} ({me.phone})")

    # Завантаження конфігу
    targets = load_config()
    log(f"📋 Завантажено {len(targets)} груп для розсилки")
    for t in targets:
        log(f"   → {t['group']} (пауза {t.get('delay_min', 60)}-{t.get('delay_max', 180)} сек)")

    # Завантаження діалогів (для пошуку ID)
    log("📥 Завантаження списку чатів...")
    try:
        await client.get_dialogs()
    except Exception:
        pass

    # Stop event для graceful shutdown
    stop_event = asyncio.Event()

    def handle_signal():
        log("🛑 Отримано сигнал зупинки. Завершення...")
        stop_event.set()

    # Обробка SIGTERM (Railway надсилає при зупинці)
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows не підтримує add_signal_handler
            pass

    # Запуск паралельних циклів розсилки
    send_lock = asyncio.Lock()
    tasks = []
    for target_data in targets:
        tasks.append(asyncio.create_task(
            group_sender_loop(client, target_data, send_lock, stop_event)
        ))

    log("🚀 Розсилку запущено!")

    await asyncio.gather(*tasks)

    log("🏁 Розсилку зупинено.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
