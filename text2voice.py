import gtts
import os
import uuid

AUDIO_DIR = os.path.dirname(__file__) + "/audio"


def generate_unique_name():
    uuid_value = uuid.uuid4()
    return f"{str(uuid_value)}"


def convert_text_to_speech(text, language_code='ru'):
    output_filepath = os.path.join(AUDIO_DIR, f"{generate_unique_name()}.mp3")
    tts = gtts.gTTS(text=text, lang=language_code)
    tts.save(output_filepath)
    return output_filepath


