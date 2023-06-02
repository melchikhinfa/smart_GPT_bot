import os
import logging
import openai
import uuid
import pydub
import telegram
from smart_GPT_bot.file_proc import FileProcessing
from telegram.ext import filters
import dotenv
from functools import wraps

# TODO: Хранение истории сообщений в БД

dotenv.load_dotenv()
AUDIO_DIR = os.path.dirname(__file__) + "/audio"
OPENAI_TOKEN = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("API_TELEGRAM")


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

question = ''
history = []
doc_proc = None


class TelegramBot:

    def __init__(self, token):
        self.token = token


def send_action(action):
    """Sends typing action while processing func command."""

    def decorator(func):
        @wraps(func)
        async def command_func(self, update, context, *args, **kwargs):
            await context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=action)
            return await func(self, update, context, *args, **kwargs)

        return command_func

    return decorator


def generate_unique_name():
    """Генерирует имя файла для аудио"""
    uuid_value = uuid.uuid4()
    return f"{str(uuid_value)}"


def voice_to_text(audiofile_path):
    with open(audiofile_path, "rb") as audio:
        transcripted_voice = openai.Audio.transcribe("whisper-1", audio)
        return transcripted_voice["text"]


async def get_voice_ogg(voice):
    voice_file = await voice.get_file()
    ogg_filepath = os.path.join(AUDIO_DIR, f"{generate_unique_name()}.ogg")
    await voice_file.download_to_drive(ogg_filepath)
    return ogg_filepath


def ogg_to_mp3(ogg_filepath):
    mp3_filepath = os.path.join(AUDIO_DIR, f"{generate_unique_name()}.mp3")
    audio = pydub.AudioSegment.from_file(ogg_filepath, format="ogg")
    audio.export(mp3_filepath, format="mp3")
    return mp3_filepath


def generate_response(text):
    model = os.getenv("GPT3_MODEL")
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "user", "content": text}
        ]
    )
    answer = response["choices"][0]["message"]["content"]
    return answer


async def handle_document(update: telegram.Update,
                          context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    global question, history, doc_proc
    doc_message = update.message.document
    if doc_message is not None:
        file_name = doc_message.file_name
        file_id = doc_message.file_id
        path_file = await doc_message.get_file()
        local_path = f"./storage/loaded_data/{file_name}"
        file_download = await path_file.download_to_drive(local_path)
        file_size = os.path.getsize(local_path)
        logger.info(f"File: {file_name} ({file_id}) of size {file_size} downloaded.")
        await update.message.reply_text(f"Файл {file_name} загружен для анализа. Размер {file_size} байт.")
        answer_proc = FileProcessing()
        doc_proc = answer_proc.doc_loader(local_path)
        answer = answer_proc.get_result(doc_proc, question)
        history.append({'role': "assistant", "content": answer})
        await update.message.reply_text(answer)


async def help_command(update: telegram.Update,
                       context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    help_message = f"Привет, {user.mention_html()}!\n\n"
    help_message += "Можем общаться текстом или голосовыми сообщениями.\n\n"
    help_message += "Используй /read[text] если необходимо прочитать сообщение.\n"
    help_message += "Используй /help чтобы я повторил это сообщение! \n\n"
    help_message += "А теперь можешь задать свой вопрос \U0001F916"  # robot face emoji

    await update.message.reply_html(
        text=help_message,
        reply_markup=telegram.ForceReply(selective=True),
    )


async def handle_text(update: telegram.Update,
                      context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    global question
    text = update.message.text
    await handle_document(update, context)
    if text.startswith("#"):
        question = text
        await handle_document(update, context)
    else:
        answer = generate_response(text)
        await update.message.reply_text(answer)


async def handle_voice(update: telegram.Update,
                       context: telegram.ext.ContextTypes.DEFAULT_TYPE) -> None:
    ogg_filepath = await get_voice_ogg(update.message.voice)
    mp3_filepath = ogg_to_mp3(ogg_filepath)
    transcripted_text = voice_to_text(mp3_filepath)
    await update.message.reply_text("Ваш запрос: \n" + transcripted_text)
    answer = generate_response(transcripted_text)
    await update.message.reply_text(answer)
    os.remove(ogg_filepath)
    os.remove(mp3_filepath)


def main():
    if not os.path.exists(AUDIO_DIR):
        os.mkdir(AUDIO_DIR)
    openai.api_key = OPENAI_TOKEN
    mode = os.getenv("MODE")
    if mode == 'webhook':
        bot = telegram.ext.Application.builder().token(TELEGRAM_TOKEN).webhook_url(os.getenv("WEBHOOK_URL")).build()
        bot.run_webhook()
    elif mode == 'polling':
        bot = telegram.ext.Application.builder().token(TELEGRAM_TOKEN).build()
        # bot.add_handler(telegram.ext.CommandHandler("read", read_command))
        bot.add_handler(telegram.ext.CommandHandler("help", help_command))
        bot.add_handler(telegram.ext.MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        bot.add_handler(telegram.ext.MessageHandler(filters.Document.ALL, handle_document))
        bot.add_handler(telegram.ext.MessageHandler(filters.VOICE, handle_voice))

        bot.run_polling()


if __name__ == "__main__":
    main()
