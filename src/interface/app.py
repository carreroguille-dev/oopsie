"""Gradio interface for Oopsie — thin layer, no business logic."""

import gradio as gr

from src.agent.core import OopsieAgent
from src.voice.transcriber import Transcriber

THEME = gr.themes.Soft(primary_hue="orange", neutral_hue="gray")


def create_app(agent: OopsieAgent, transcriber: Transcriber | None = None,
               server_name: str = "0.0.0.0", server_port: int = 7860) -> gr.Blocks:
    """Create and return the Gradio app (without launching it)."""

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
                return "", history
            history.append({"role": "user", "content": message})
            response = agent.process_message(message)
            history.append({"role": "assistant", "content": response})
            return "", history

        def handle_audio(audio_path: str | None, history: list[dict]) -> tuple:
            if not audio_path or not transcriber:
                return None, history
            text = transcriber.transcribe(audio_path)
            if not text.strip():
                return None, history
            history.append({"role": "user", "content": f"🎤 {text}"})
            response = agent.process_message(text)
            history.append({"role": "assistant", "content": response})
            return None, history

        def reset_chat() -> list[dict]:
            agent.reset()
            return [{"role": "assistant", "content": "¡Chat reiniciado! ¿En qué te ayudo?"}]

        # Wire events
        send_btn.click(handle_text, [text_input, chatbot], [text_input, chatbot])
        text_input.submit(handle_text, [text_input, chatbot], [text_input, chatbot])
        audio_input.stop_recording(handle_audio, [audio_input, chatbot], [audio_input, chatbot])
        new_chat_btn.click(reset_chat, outputs=[chatbot])

    return app
