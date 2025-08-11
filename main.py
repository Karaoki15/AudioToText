import os
import logging
import random
import string
import asyncio
from pydub import AudioSegment
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor
from faker import Faker
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)

API_TOKEN = ''
MAX_MESSAGE_LENGTH = 4096

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

audio_dir = 'audio_files'
if not os.path.exists(audio_dir):
    os.makedirs(audio_dir)

processing_queue = []
user_restore_audio_preferences = {}
current_task_cancelled = False

fake = Faker()

def generate_random_filename(extension, length=15):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return f"{random_string}.{extension}"

def get_audio_duration(audio_path):
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000

def calculate_transcription_wait_time(audio_duration):
    if audio_duration <= 5 * 60:
        return 1.5 * 60
    elif audio_duration <= 12 * 60:
        return 3 * 60
    elif audio_duration <= 16 * 60:
        return 4 * 60
    elif audio_duration <= 30 * 60:
        return 8 * 60
    elif audio_duration <= 60 * 60:
        return 13 * 60
    else:
        return 19 * 60

def generate_new_user_credentials():
    email = fake.email()
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return email, password

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    global current_task_cancelled
    current_task_cancelled = False
    logging.info("Команда /start получена")
    user_id = message.from_user.id
    user_restore_audio_preferences[user_id] = False
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    button_text = "Разбирать с AI"
    markup.add(KeyboardButton(text=button_text))
    markup.add(KeyboardButton(text="Отмена"))
    await message.reply("Привет! Я бот, который поможет вам распознать аудиосообщения. Отправьте мне голосовое сообщение или аудиофайл в формате MP3, OGG, WAV или WMA, и я преобразую его в текст.", reply_markup=markup)

@dp.message_handler(Text(equals="Отмена"))
async def cancel_current_task(message: types.Message):
    global current_task_cancelled
    current_task_cancelled = True
    await message.reply("Текущая задача была отменена, если вы нажали отмена во время разбора аудио вам прийдется подождать, но текст вам не прийдет.")

@dp.message_handler(Text(startswith="Разбирать с AI"))
async def toggle_restore_audio(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_restore_audio_preferences:
        user_restore_audio_preferences[user_id] = False

    user_restore_audio_preferences[user_id] = not user_restore_audio_preferences[user_id]
    button_text = "Разбирать с AI" + (" ✅" if user_restore_audio_preferences[user_id] else "")

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(text=button_text))
    markup.add(KeyboardButton(text="Отмена"))
    await message.reply(f"Выбор опции изменен на {'включен ✅' if user_restore_audio_preferences[user_id] else 'выключен ❌'}.", reply_markup=markup)

@dp.message_handler(content_types=['voice', 'audio', 'document'])
async def handle_audio_message(message: types.Message):
    logging.info("Получено голосовое или аудиосообщение от пользователя")
    user_id = message.from_user.id
    restore_audio = user_restore_audio_preferences.get(user_id, False)

    try:
        # Определение типа файла и его расширения
        if message.content_type == 'voice':
            file_info = await bot.get_file(message.voice.file_id)
            file_extension = 'ogg'
        elif message.content_type == 'audio':
            file_info = await bot.get_file(message.audio.file_id)
            file_extension = message.audio.file_name.split('.')[-1]
        elif message.content_type == 'document':
            file_info = await bot.get_file(message.document.file_id)
            file_extension = message.document.file_name.split('.')[-1]
            if file_extension not in ['wav', 'mp3', 'ogg', 'wma']:
                await message.reply("Файл не поддерживается. Пожалуйста, отправьте файл в формате MP3, OGG, WAV или WMA.")
                return
        else:
            await message.reply("Файл не поддерживается. Пожалуйста, отправьте аудиофайл в формате MP3, OGG, WAV или WMA.")
            return

        logging.info(f"file_info: {file_info}")

        file = await bot.download_file(file_info.file_path)

        random_file_name = generate_random_filename(file_extension)
        audio_path = os.path.join(audio_dir, random_file_name)

        with open(audio_path, 'wb') as audio_file:
            audio_file.write(file.getvalue())

        logging.info("Аудиофайл сохранен")

        # Вычисление длительности аудиофайла
        audio_duration = get_audio_duration(audio_path)
        logging.info(f"Длительность аудиофайла: {audio_duration} секунд")

        # Определение времени ожидания в зависимости от длительности аудиофайла
        transcription_wait_time = calculate_transcription_wait_time(audio_duration)
        logging.info(f"Время ожидания транскрипции: {transcription_wait_time} секунд")

        # Добавление задания в очередь
        processing_queue.append((message, audio_path, random_file_name, transcription_wait_time, restore_audio))
        logging.info("Задание добавлено в очередь")
        if len(processing_queue) <= 5:
            asyncio.create_task(process_next_in_queue())

    except Exception as e:
        await message.reply(f'Ошибка при распознавании текста: {str(e)}')
        logging.error(f"Ошибка при распознавании текста: {str(e)}")

async def process_next_in_queue():
    global current_task_cancelled
    while processing_queue:
        message, audio_path, random_file_name, wait_time, restore_audio = processing_queue.pop(0)

        try:
            status_message = await bot.send_message(message.chat.id, f"Загрука файла и настройка его.")
            await asyncio.sleep(8)

            if current_task_cancelled:
                await bot.send_message(message.chat.id, "Задача была отменена.")
                current_task_cancelled = False
                continue

            text = await upload_and_get_text_from_turboscribe(audio_path, status_message, message.chat.id, random_file_name, wait_time, restore_audio)

            if current_task_cancelled:
                await bot.send_message(message.chat.id, "Задача была отменена.")
                current_task_cancelled = False
                continue

            if text is None:
                await bot.send_message(message.chat.id, "Не удалось получить текст транскрипции.")
            else:
                logging.info("Отправка текста пользователю")
                await send_text_in_parts(message, text)
                logging.info("Текст отправлен пользователю")

            await bot.send_message(message.chat.id, "Файл разобран. Если вы отправили несколько файлов, пожалуйста, подождите. Если нет, вы можете отправить еще аудиофайлы для обработки.")

        except Exception as e:
            if not current_task_cancelled:
                await bot.send_message(message.chat.id, f'Ошибка при распознавании текста: {str(e)}')
            logging.error(f"Ошибка при распознавании текста: {str(e)}")

        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logging.info("Временный аудиофайл удален")

async def send_text_in_parts(message: types.Message, text: str):
    chat_id = message.chat.id
    if text.strip():
        for i in range(0, len(text), MAX_MESSAGE_LENGTH):
            logging.info(f"Отправка части текста: {i}-{i+MAX_MESSAGE_LENGTH}")
            await bot.send_message(chat_id, text[i:i+MAX_MESSAGE_LENGTH], reply_to_message_id=message.message_id)
    else:
        await bot.send_message(chat_id, "Текст транскрипции пуст.")

async def edit_message_text_if_different(chat_id, message_id, text):
    try:
        current_message = await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception as e:
        if "Message is not modified" in str(e):
            logging.info("Сообщение не было изменено, так как новый текст совпадает с текущим")
        else:
            raise e

async def wait_for_transcription(driver, wait_time, random_file_name):
    elapsed_time = 0
    check_interval = 30  # Проверять каждые 30 секунд
    while elapsed_time < wait_time:
        if current_task_cancelled:
            return None
        await asyncio.sleep(check_interval)
        elapsed_time += check_interval
        logging.info(f"Ожидание завершения транскрипции: прошло {elapsed_time} секунд")

        try:
            # Обновление списка файлов
            driver.refresh()
            await asyncio.sleep(5)

            file_name_no_ext = os.path.splitext(random_file_name)[0]
            file_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'block hover:underline')]")
            for file_link in file_links:
                if file_name_no_ext in file_link.text:
                    file_link.click()
                    logging.info("Файл найден и нажат для извлечения текста")
                    await asyncio.sleep(5)
                    # Проверка на наличие текста транскрипции на странице
                    transcript_container = driver.find_element(By.XPATH, "//div[@class='flex flex-col space-y-4']")
                    if transcript_container.text.strip():
                        logging.info("Транскрипция завершена")
                        return transcript_container.text
                    return transcript_container.text  # Выход из цикла, если файл найден и проверен
        except NoSuchElementException:
            pass

    logging.info("Транскрипция не завершена в течение отведенного времени")
    return None

async def upload_and_get_text_from_turboscribe(audio_path, status_message, chat_id, random_file_name, wait_time, restore_audio):
    global current_task_cancelled
    logging.info("Запуск браузера и открытие страницы...")

    email, password = generate_new_user_credentials()
    
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-features=NetworkService')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-site-isolation-trials')
    options.add_argument('log-level=3')
    prefs = {
        "profile.default_content_setting_values.cookies": 1,
        "profile.block_third_party_cookies": False
    }
    options.add_experimental_option("prefs", prefs)
    
    # Генерация случайного User-Agent
    user_agent = fake.user_agent()
    options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(options=options)

    try:
        driver.get('https://turboscribe.ai/register')
        logging.info("Открытие страницы: https://turboscribe.ai/register")

        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.NAME, 'email')))
        email_field = driver.find_element(By.NAME, 'email')
        password_field = driver.find_element(By.NAME, 'password')

        logging.info("Ввод email и пароля для регистрации нового аккаунта")
        email_field.send_keys(email)
        password_field.send_keys(password)

        register_button = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, "//button[@type='submit' and contains(@class, 'w-full dui-btn dui-btn-primary')]")))
        logging.info("Нажатие на кнопку регистрации")
        register_button.click()

        WebDriverWait(driver, 60).until(EC.url_contains("dashboard"))
        logging.info("Перенаправление после регистрации прошло успешно")

        await edit_message_text_if_different(chat_id, status_message.message_id, "Идет транскрипция, жди")
        await asyncio.sleep(8)

        transcribe_button = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Transcribe Your First File')]")))
        logging.info("Кнопка 'Transcribe Your First File' найдена")
        transcribe_button.click()

        # Найдите элемент выпадающего списка
        select_element = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.NAME, 'language')))
        select = Select(select_element)

        # Выберите "Russian" по значению
        select.select_by_value('Russian')
        logging.info("Язык аудио выбран: Russian")

        more_settings_button = driver.find_element(By.XPATH, "//span[text()='Speaker Recognition & More Settings']")
        more_settings_button.click()

        logging.info("Выбор опции 'Recognize Speakers'")
        recognize_speakers_checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox' and @name='bool:diarize?']")
        if not recognize_speakers_checkbox.is_selected():
            recognize_speakers_checkbox.click()

        if restore_audio:
            logging.info("Выбор опции 'restore audio'")
            restore_audio_checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox' and @name='bool:clean-up-audio?']")
            if not restore_audio_checkbox.is_selected():
                restore_audio_checkbox.click()

        # Загрузка файла
        upload_element = driver.find_element(By.XPATH, "//input[@type='file' and @class='dz-hidden-input']")
        upload_element.send_keys(os.path.abspath(audio_path))
        await asyncio.sleep(20)

        transcribe_button = WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.XPATH, "//button[@type='submit' and contains(@class, 'dui-btn-primary') and contains(@class, 'w-full')]")))
        transcribe_button.click()
        logging.info("Нажатие кнопки 'TRANSCRIBE'")
        await asyncio.sleep(3)

        logging.info("Ожидание завершения обработки")
        await edit_message_text_if_different(chat_id, status_message.message_id, "Идет транскрипция, жди")
        text = await wait_for_transcription(driver, wait_time, random_file_name)

        if current_task_cancelled:
            await bot.send_message(chat_id, "Задача была отменена.")
            current_task_cancelled = False
            return

        if text is None:
            await bot.send_message(chat_id, "Не удалось получить текст транскрипции.")
        else:
            logging.info("Транскрипция завершена, текст извлечен")
            return text

    finally:
        driver.quit()
        logging.info("Браузер закрыт")

if __name__ == "__main__":
    logging.info("Запуск бота")
    executor.start_polling(dp, skip_updates=True)