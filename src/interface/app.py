"""Gradio interface for Oopsie — thin layer, no business logic."""

import logging

import gradio as gr

from src.agent.core import OopsieAgent
from src.voice.transcriber import Transcriber

logger = logging.getLogger(__name__)

THEME = gr.themes.Soft(primary_hue="orange", neutral_hue="gray")


def create_app(agent: OopsieAgent, transcriber: Transcriber | None = None,
               server_name: str = "0.0.0.0", server_port: int = 7860) -> gr.Blocks:
    """Create and return the Gradio app (without launching it)."""
    logger.info("Creating Gradio app with server_name=%s, server_port=%d", server_name, server_port)

    with gr.Blocks(title="Oopsie") as app:
        gr.Markdown("## 🐣 Oopsie")
        gr.Markdown("Tu asistente personal de tareas")

        chatbot = gr.Chatbot(
            value=[{"role": "assistant", "content": "¡Hola! Soy Oopsie, tu asistente de tareas. ¿En qué te ayudo?"}],
            height=450,
        )

        with gr.Row():
            text_input = gr.Textbox(
                placeholder="Escribe algo... (ej: 'Crea un espacio Universidad')",
                show_label=False,
                scale=4,
            )
            send_btn = gr.Button("Enviar", scale=1, variant="primary")

        audio_input = gr.Audio(
            sources=["microphone"],
            type="filepath",
            label="O habla...",
        )

        new_chat_btn = gr.Button("Nueva conversación", variant="secondary", size="sm")

        # --- Event handlers ---

        def handle_text(message: str, history: list[dict]) -> tuple:
            if not message.strip():
                logger.debug("Received empty text message in Gradio, ignoring")
                return "", history

            logger.info("Gradio text message received (length=%d chars)", len(message))
            history.append({"role": "user", "content": message})

            try:
                response = agent.process_message(message)
                history.append({"role": "assistant", "content": response})
                logger.info("Gradio response generated (length=%d chars)", len(response))
            except Exception as e:
                logger.error("Failed to process Gradio text message", exc_info=True)
                history.append({"role": "assistant", "content": "Lo siento, ocurrió un error al procesar tu mensaje."})

            return "", history

        def handle_audio(audio_path: str | None, history: list[dict]) -> tuple:
            if not audio_path:
                logger.debug("No audio path provided")
                return None, history

            if not transcriber:
                logger.warning("Audio received but transcriber not available")
                return None, history

            logger.info("Gradio audio message received: %s", audio_path)

            try:
                text = transcriber.transcribe(audio_path)
                if not text.strip():
                    logger.warning("Empty transcription from audio")
                    return None, history

                logger.info("Audio transcribed: '%s'", text)
                history.append({"role": "user", "content": f"🎤 {text}"})
                response = agent.process_message(text)
                history.append({"role": "assistant", "content": response})
                logger.info("Gradio audio response generated")
            except Exception as e:
                logger.error("Failed to process Gradio audio message", exc_info=True)
                history.append({"role": "assistant", "content": "Lo siento, ocurrió un error al procesar tu mensaje de voz."})

            return None, history

        def reset_chat() -> list[dict]:
            logger.info("Gradio chat reset requested")
            agent.reset()
            return [{"role": "assistant", "content": "¡Chat reiniciado! ¿En qué te ayudo?"}]

        # Wire events
        send_btn.click(handle_text, [text_input, chatbot], [text_input, chatbot])
        text_input.submit(handle_text, [text_input, chatbot], [text_input, chatbot])
        audio_input.stop_recording(handle_audio, [audio_input, chatbot], [audio_input, chatbot])
        new_chat_btn.click(reset_chat, outputs=[chatbot])

    logger.info("Gradio app created successfully")
    return app
