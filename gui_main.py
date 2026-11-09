import logging
from jarvis.config import load_config
from jarvis.model import ensure_model
from jarvis.stt import Listener
from jarvis.tts import Speaker
from jarvis.intents import IntentHandler
from jarvis.apps import build_apps
from jarvis.main import Jarvis, BASE_DIR, setup_logging
from jarvis.tray import build_tray

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

    # 4. Инициализация Графического окна
    app = PhoenixGUI(
        jarvis,
        BASE_DIR / "config.json",
        on_command_cb=worker.process_command_async,
        on_mic_toggle_cb=worker.set_listening,
        on_voice_change_cb=worker.reload_voice,
        on_model_change_cb=worker.reload_model,
    )

    # 5. Трей (в отдельном daemon-потоке, не блокирует mainloop)
    tray = None
    try:
        tray = build_tray(
            jarvis,
            on_quit=lambda: app.after(0, app.destroy),
            on_clear_dialog=worker.clear_dialog,
        )
        tray.run_detached()
    except Exception:
        logging.getLogger("jarvis").exception("Не удалось создать иконку в трее")

    # 6. Фоновые задачи + приветствие + главный цикл
    worker.start_background_tasks()
    jarvis.say("Феникс запущен и готов к работе.")

    try:
        app.mainloop()
    finally:
        # Сохраняем историю диалога на диск перед выходом
        try:
            jarvis.handler.save_dialog()
        except Exception:
            logging.getLogger("jarvis").exception("Не удалось сохранить историю диалога")
        # Корректно гасим трей
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
        jarvis.shutdown()


if __name__ == "__main__":
    import traceback
    from pathlib import Path

    try:
        main()
    except Exception:
        crash = Path(__file__).resolve().parent / "crash.log"
        crash.write_text(traceback.format_exc(), encoding="utf-8")
        raise
