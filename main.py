import asyncio
import os
from datetime import datetime

# Библиотеки для Telegram
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message, 
    FSInputFile, 
    InlineQuery, 
    InlineQueryResultAudio, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)

# Библиотека для Яндекс Музыки
from yandex_music import ClientAsync

# --- КОНФИГ ---
TG_TOKEN = '8091769810:AAEnp4S_x8n8Kjn5y9PVsBF4yZOWa5xFXWc'
YANDEX_TOKEN = 'y0__xCP54a-CBje-AYg2bqDqhYwmueGvggbgX4mbHLvZWeA-rxaB7aAJte56w'

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
yandex_client = ClientAsync(YANDEX_TOKEN)

# Логирование в консоль
def log_request(user: types.User, query: str, mode: str):
    time = datetime.now().strftime("%H:%M:%S")
    username = f"@{user.username}" if user.username else f"ID: {user.id}"
    print(f"[{time}] [{mode}] {username} -> {query}")

# 1. ПОИСК И ВЫВОД СПИСКА КНОПОК
@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    await message.answer("Дарова кароче ты мне название песни а я тебе 5 вариантов")

@dp.message(F.text)
async def search_and_list(message: Message):
    query = message.text
    log_request(message.from_user, query, "SEARCH")

    try:
        search_result = await yandex_client.search(query)
        
        if not search_result.tracks or not search_result.tracks.results:
            await message.answer("Ниче нету. Другое название скажи.")
            return

        tracks = search_result.tracks.results[:5]
        builder = []
        
        for track in tracks:
            artist = track.artists[0].name if track.artists else "Неизвестен"
            button_text = f"{artist} - {track.title}"
            # Ограничиваем длину текста на кнопке, чтобы она не была слишком огромной
            if len(button_text) > 50:
                button_text = button_text[:47] + "..."
            
            # Используем префикс "dl:" и ID трека
            builder.append([InlineKeyboardButton(text=button_text, callback_data=f"dl:{track.id}")])

        keyboard = InlineKeyboardMarkup(inline_keyboard=builder)
        await message.answer("Выбери нужную:", reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка поиска: {e}")
        await message.answer("Ошибка при поиске. Попробуй позже.")

# 2. ОБРАБОТКА НАЖАТИЯ НА КНОПКУ (СКАЧИВАНИЕ)
@dp.callback_query(F.data.startswith("dl:"))
async def download_track(callback: CallbackQuery):
    # Извлекаем ID (все что после двоеточия)
    track_id = callback.data.split(":")[1]
    
    await callback.answer("Гружу...")
    status_msg = await callback.message.answer("Качаю...")

    try:
        # Получаем данные трека
        tracks = await yandex_client.tracks([track_id])
        track = tracks[0]
        
        log_request(callback.from_user, f"{track.title}", "DOWNLOAD")

        # Имя файла делаем уникальным через ID
        file_name = f"track_{track.id}.mp3"
        
        # Скачиваем (192 kbps если доступно)
        await track.download_async(file_name, bitrate_in_kbps=192)

        # Отправляем аудио
        audio = FSInputFile(file_name)
        await callback.message.answer_audio(
            audio=audio,
            performer=track.artists[0].name if track.artists else "Unknown",
            title=track.title
        )
        
        # Чистим за собой
        await status_msg.delete()
        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        print(f"Ошибка загрузки: {e}")
        await status_msg.edit_text("Не удалось скачать файл. Возможно, он защищен или недоступен.")

# 3. ИНЛАЙН-РЕЖИМ
@dp.inline_query()
async def inline_handler(query: InlineQuery):
    if not query.query:
        return
    
    log_request(query.from_user, query.query, "INLINE")
    
    try:
        search = await yandex_client.search(query.query)
        results = []
        
        if search.tracks and search.tracks.results:
            for t in search.tracks.results[:10]:
                try:
                    info = await t.get_download_info_async()
                    # Ищем лучший битрейт
                    best_link = await info[0].get_direct_link_async()
                    
                    results.append(InlineQueryResultAudio(
                        id=f"in_{t.id}",
                        audio_url=best_link,
                        title=t.title,
                        performer=t.artists[0].name if t.artists else "Unknown"
                    ))
                except:
                    continue
        
        await query.answer(results, cache_time=60)
    except Exception as e:
        print(f"Inline error: {e}")

# ЗАПУСК
async def main():
    # Отключаем проверку SSL для Windows
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    
    await yandex_client.init()
    print("\n" + "="*40)
    print("БОТ УСПЕШНО ЗАПУЩЕН!")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*40 + "\n")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Бот остановлен пользователем.")