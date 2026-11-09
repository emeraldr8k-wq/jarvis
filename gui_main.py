import logging
from jarvis.config import load_config
from jarvis.model import ensure_model
from jarvis.stt import Listener
from jarvis.tts import Speaker
from jarvis.intents import IntentHandler
from jarvis.apps import build_apps
from jarvis.main import Jarvis, BASE_DIR, setup_logging

# Импортируем наши новые раздельные модули
from gui_app import PhoenixGUI, gui_queue
from gui_worker import PhoenixWorker


def main():
    # 1. Запуск логирования в файл
    setup_logging()

    # 2. Инициализация ядра ассистента
    config = load_config(BASE_DIR)
    model_dir = ensure_model(BASE_DIR / "models")
    config["use_whisper"] = False  # Работаем на точном Vosk

    if config.get("use_llm", True):
        from jarvis.brain import Brain
        brain = Brain(config.get("llm_model", "qwen2.5:1.5b"), config.get("ollama_url", "http://127.0.0.1:11434"))

    speaker = Speaker(config)
    listener = Listener(model_dir, config["sample_rate"], config.get("input_device"))
    handler = IntentHandler(config, build_apps(config), brain)
    jarvis = Jarvis(config, listener, speaker, handler, BASE_DIR, None)

    # 3. Инициализация логического Воркера
    worker = PhoenixWorker(jarvis, gui_queue)

    # 4. Инициализация Графического окна (передаем воркер в качестве обработчика)
    app = PhoenixGUI(jarvis, BASE_DIR / "config.json", on_command_cb=worker.process_command_async)

    # 5. Запуск фоновых задач микрофона и старт приложения
    worker.start_background_tasks()
    jarvis.say("Феникс запущен и готов к работе.")

    app.mainloop()
    jarvis.shutdown()


if __name__ == "__main__":
    main()
