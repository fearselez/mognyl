import asyncio
import os
import random
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

class SenderCore:
    def __init__(self, log_callback):
        self.client = TelegramClient('sender_session', int(API_ID), API_HASH)
        self.log = log_callback
        self.is_running = False
        self.phone = None
        self.phone_code_hash = None

    async def _connect_if_needed(self):
        if not self.client.is_connected():
            await self.client.connect()

    async def is_authorized(self):
        await self._connect_if_needed()
        return await self.client.is_user_authorized()

    async def send_code(self, phone):
        self.phone = phone
        await self._connect_if_needed()
        result = await self.client.send_code_request(phone)
        self.phone_code_hash = result.phone_code_hash
        return True

    async def submit_code(self, code):
        await self._connect_if_needed()
        try:
            await self.client.sign_in(self.phone, code, phone_code_hash=self.phone_code_hash)
            return True, "Успішна авторизація!"
        except SessionPasswordNeededError:
            return False, "У вас встановлений 2FA (двоетапна перевірка). Зверніться до розробника для додавання підтримки."
        except Exception as e:
            return False, str(e)

    async def stop(self):
        self.is_running = False

    async def start_sending(self, targets):
        self.is_running = True
        self.log("🚀 Розсилку запущено (паралельний режим)!")
        
        await self._connect_if_needed()
        if not await self.client.is_user_authorized():
            self.log("❌ Помилка: Ви не авторизовані!")
            return

        self.log("📥 Завантаження списку ваших чатів (пошук ID)...")
        try:
            await self.client.get_dialogs()
        except Exception as e:
            pass

        send_lock = asyncio.Lock()
        tasks = []
        for target_data in targets:
            tasks.append(asyncio.create_task(self._group_sender_loop(target_data, send_lock)))
            
        if not tasks:
            self.log("Немає груп для відправки.")
            self.is_running = False
            return
            
        # Чекаємо завершення всіх паралельних циклів відправки
        await asyncio.gather(*tasks)
        self.log("🏁 Розсилку повністю зупинено.")

    async def _group_sender_loop(self, target_data, send_lock):
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
            
        while self.is_running:
            # Спроба відправки (з глобальним локом щоб уникнути одночасної відправки в секунду)
            async with send_lock:
                if not self.is_running: break
                self.log(f"🔄 Відправка в {group_str}...")
                try:
                    entity = await self.client.get_entity(target)
                    await self.client.send_message(entity, message)
                    self.log(f"✅ Успішно відправлено в {group_str}")
                except Exception as e:
                    self.log(f"❌ Помилка з {group_str}: {str(e)}")
                    
                # Мікро-пауза після кожної відправки (захист від спаму Telethon)
                await asyncio.sleep(1.5)
                
            if not self.is_running: break
            
            delay = random.randint(delay_min, delay_max)
            self.log(f"⏳ Очікування {delay} сек. для групи {group_str}...")
            
            # Робимо паузу з кроком 1 сек, щоб можна було швидко перервати її при зупинці
            for _ in range(delay):
                if not self.is_running:
                    break
                await asyncio.sleep(1)
