import threading
import logging
from jarvis.main import Jarvis

log = logging.getLogger("jarvis")


class PhoenixWorker:
    def __init__(self, jarvis_instance, gui_queue):
        self.jarvis = jarvis_instance
        self.gui_queue = gui_queue

    def start_background_tasks(self):
        """Запуск фонового потока для прослушивания микрофона Vosk"""
        threading.Thread(target=self._voice_listener_loop, daemon=True, name="voice-stt").start()

    def set_listening(self, enabled: bool):
        """Включает/выключает обработку голосовых команд (поток Vosk остаётся жив)."""
        self.jarvis.listening_enabled = enabled
        log.info("Микрофон %s", "включён" if enabled else "выключен")
        if not enabled:
            # Сбрасываем накопленный буфер, чтобы при включении
            # не сработала фраза, произнесённая в «выключенном» состоянии
            try:
                self.jarvis.listener.flush()
            except Exception:
                log.exception("Не удалось сбросить буфер микрофона")

    def process_command_async(self, text: str, is_voice: bool = False):
        """Запуск обработки команды в отдельном потоке, чтобы GUI не зависал"""
        if not is_voice:
            log.info("Текстовый ввод пользователя: %r", text)
        threading.Thread(target=self._execute_command, args=(text,), daemon=True).start()

    def _execute_command(self, text: str):
        # Прогоняем команду через стандартный IntentHandler (приложения будут запускаться!)
        response = self.jarvis.handler.handle(text)

        # Передаем ответ обратно в очередь графического окна
        self.gui_queue.put(("Феникс", response))
        self.jarvis.say(response)

    def _voice_listener_loop(self):
        try:
            for phrase, audio in self.jarvis.listener.phrases(self.jarvis.stop_event):
                if not self.jarvis.listening_enabled:
                    continue
                cmd = self.jarvis._extract_command(phrase.lower())
                if cmd:
                    self.gui_queue.put(("Вы (Голос)", cmd))
                    self.process_command_async(cmd, is_voice=True)
        except Exception as e:
            log.exception("Критическая ошибка в аудиопотоке: %s", e)
