import logging
from pathlib import Path

from openai import OpenAI

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, api_key: str, base_url: str, model: str, language: str):
        self._model = model
        self._language = language
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info("Transcriber initialized (model=%s, language=%s)", model, language)

    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            result = self._client.audio.transcriptions.create(
                model=self._model,
                file=f,
                language=self._language,
                response_format="text",
            )
        text = result.strip() if isinstance(result, str) else result.text.strip()
        logger.info("Transcribed '%s' → '%s'", Path(audio_path).name, text[:80])
        return text
