import os
import logging
import pyttsx3
from dotenv import load_dotenv
import speech_recognition as sr

load_dotenv()


MIC_INDEX_STR = (os.getenv("MIC_INDEX") or "").strip()
MIC_INDEX = int(MIC_INDEX_STR) if MIC_INDEX_STR else None

recognizer = sr.Recognizer()
mic = sr.Microphone(device_index=MIC_INDEX)
_ambient_calibrated = False


# TTS setup
def speak_text(text: str):
    try:
        engine = pyttsx3.init()
        for voice in engine.getProperty("voices"):
            if "Flo (English (UK))" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logging.error(f"❌ TTS failed: {e}")


def transcribe_speech(
    timeout: float | None = 5, phrase_time_limit: float | None = 15
) -> str | None:
    """Listen on the configured microphone and return recognized text, or None if not heard/understood."""

    global _ambient_calibrated

    try:
        with mic as source:
            if not _ambient_calibrated:
                # Calibrate once to reduce background noise impact.
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                _ambient_calibrated = True

            audio = recognizer.listen(
                source, timeout=timeout, phrase_time_limit=phrase_time_limit
            )
    except sr.WaitTimeoutError:
        logging.info("No speech detected before timeout.")
        return None
    except Exception as exc:
        logging.error(f"Listening failed: {exc}")
        return None

    try:
        return recognizer.recognize_google(audio).strip()
    except sr.UnknownValueError:
        logging.info("Speech was unintelligible.")
    except Exception as exc:
        logging.error(f"Speech recognition failed: {exc}")

    return None
