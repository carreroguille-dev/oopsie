"""Speech-to-text using Faster-Whisper."""

from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str = "small", language: str = "es"):
        self.language = language
        self.model = WhisperModel(model_size, compute_type="int8")

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file to text."""
        segments, _ = self.model.transcribe(audio_path, language=self.language)
        return " ".join(segment.text.strip() for segment in segments)
