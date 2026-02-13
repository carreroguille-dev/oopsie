import logging

from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model_size: str = "small", language: str = "es"):
        logger.info("Initializing Transcriber with model_size=%s, language=%s", model_size, language)
        self.language = language
        try:
            self.model = WhisperModel(model_size, compute_type="int8")
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error("Failed to load Whisper model", exc_info=True)
            raise

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file to text."""
        logger.debug("Transcribing audio file: %s", audio_path)
        try:
            segments, info = self.model.transcribe(audio_path, language=self.language)
            text = " ".join(segment.text.strip() for segment in segments)
            logger.info("Transcription completed (length=%d chars)", len(text))
            return text
        except Exception as e:
            logger.error("Failed to transcribe audio file %s", audio_path, exc_info=True)
            raise
