import os
import json
import queue
import customtkinter as ctk

# Очередь для безопасной передачи данных между потоками
gui_queue = queue.Queue()


class PhoenixGUI(ctk.CTk):
    def __init__(self, jarvis_instance, config_path, on_command_cb):
        super().__init__()
        self.jarvis = jarvis_instance
        self.config_path = config_path
        self.on_command_cb = on_command_cb  # Коллбэк для отправки команд в логику

        # Настройки главного окна
        self.title("Phoenix v1.0")
        self.geometry("780x570")
        self.resizable(False, False)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_left_panel()
        self._build_right_panel()

        self.refresh_log_view()
        self.after(100, self.check_queue)

    def _build_left_panel(self):
        """Отрисовка левой панели ассистента"""
        self.left_frame = ctk.CTkFrame(self, width=380, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        self.indicator = ctk.CTkButton(
            self.left_frame, text="", width=60, height=60, corner_radius=30,
            fg_color="#1f538d", hover_color="#2e7fd6", border_width=4, border_color="#00d2ff"
        )
        self.indicator.pack(pady=20)

        self.status_label = ctk.CTkLabel(
            self.left_frame, text="Система готова к работе, сэр",
            font=("Segoe UI", 16, "bold"), text_color="#00d2ff"
        )
        self.status_label.pack(pady=5)

        self.chat_log = ctk.CTkTextbox(
            self.left_frame, width=350, height=240, font=("Segoe UI", 13), corner_radius=10
        )
        self.chat_log.pack(pady=15)
        self.chat_log.insert("0.0", "Феникс активен.\nСлушаю ваши инструкции...\n")
        self.chat_log.configure(state="disabled")

        self.entry = ctk.CTkEntry(
            self.left_frame, width=350, height=40,
            placeholder_text="Напишите команду здесь и нажмите Enter...", corner_radius=10
        )
        self.entry.pack(pady=5)
        self.entry.bind("<Return>", self.send_text_command)

    def _build_right_panel(self):
        """Отрисовка правой панели настроек и журнала"""
        self.right_frame = ctk.CTkTabview(self, width=360, height=520)
        self.right_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")

        self.tab_config = self.right_frame.add("🔧 Настройки")
        self.tab_log = self.right_frame.add("📋 Журнал (Лог)")

        # Настройки
        self.load_current_config()
        ctk.CTkLabel(self.tab_config, text="Модель ИИ (Ollama):", font=("Segoe UI", 12, "bold")).pack(anchor="w",
                                                                                                      padx=10, pady=5)
        self.model_entry = ctk.CTkEntry(self.tab_config, width=320)
        self.model_entry.insert(0, self.current_config.get("llm_model", "qwen2.5:1.5b"))
        self.model_entry.pack(padx=10, pady=2)

        ctk.CTkLabel(self.tab_config, text="Голос ассистента (TTS):", font=("Segoe UI", 12, "bold")).pack(anchor="w",
                                                                                                          padx=10,
                                                                                                          pady=5)
        self.voice_entry = ctk.CTkEntry(self.tab_config, width=320)
        self.voice_entry.insert(0, self.current_config.get("tts_voice", "ruslan"))
        self.voice_entry.pack(padx=10, pady=2)

        self.whisper_switch = ctk.CTkSwitch(self.tab_config, text="Включить Whisper")
        if self.current_config.get("use_whisper", False):
            self.whisper_switch.select()
        self.whisper_switch.pack(anchor="w", padx=15, pady=5)

        self.save_btn = ctk.CTkButton(self.tab_config, text="Сохранить и применить", command=self.save_config_file,
                                      fg_color="#2b7337", hover_color="#399648")
        self.save_btn.pack(pady=30)

        # Журнал
        self.log_view = ctk.CTkTextbox(
            self.tab_log, width=340, height=400,
            font=("Consolas", 11), corner_radius=5,
            state="disabled"  # только для чтения, но выделение мышью работает
        )
        self.log_view.pack(padx=5, pady=5)

        # Ручная обработка копирования и выделения всего
        self.log_view.bind("<Control-c>", self._copy_log_selection)
        self.log_view.bind("<Control-a>", self._select_all_log)

        self.refresh_log_btn = ctk.CTkButton(self.tab_log, text="Обновить журнал", command=self.refresh_log_view)
        self.refresh_log_btn.pack(pady=5)

    def load_current_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.current_config = json.load(f)
            except Exception:
                self.current_config = {}

    def save_config_file(self):
        self.current_config["llm_model"] = self.model_entry.get().strip()
        self.current_config["tts_voice"] = self.voice_entry.get().strip()
        self.current_config["use_whisper"] = bool(self.whisper_switch.get())
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.current_config, f, indent=2, ensure_ascii=False)
            self.status_label.configure(text="Настройки сохранены! Перезапустите ИИ.")
        except Exception as e:
            self.status_label.configure(text=f"Ошибка сохранения: {e}")

    def refresh_log_view(self):
        # Если пользователь выделил текст — не обновляем, чтобы не сбить выделение
        try:
            if self.log_view.tag_ranges("sel"):
                return
        except Exception:
            pass

        log_file_path = os.path.join(os.path.dirname(self.config_path), "jarvis.log")

        # Временно включаем редактирование, чтобы обновить содержимое
        self.log_view.configure(state="normal")
        self.log_view.delete("0.0", "end")

        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, "r", encoding="utf-8") as f:
                    self.log_view.insert("0.0", "".join(f.readlines()[-40:]))
            except Exception as e:
                self.log_view.insert("0.0", f"Ошибка чтения лога: {e}")
        else:
            self.log_view.insert("0.0", "Журнал пуст.")

        self.log_view.configure(state="disabled")
        self.log_view.see("end")

    def append_to_log(self, sender: str, text: str):
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"\n {sender}: {text}")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def send_text_command(self, event):
        text = self.entry.get().strip()
        if text:
            self.append_to_log("Вы", text)
            self.entry.delete(0, "end")
            self.status_label.configure(text="Феникс думает...")
            self.indicator.configure(fg_color="#ff9000")
            # Передаем команду во внешний обработчик (из gui_worker)
            self.on_command_cb(text)

    def check_queue(self):
        try:
            while True:
                sender, text = gui_queue.get_nowait()
                self.append_to_log(sender, text)
                self.status_label.configure(text="Система готова к работе, сэр")
                self.indicator.configure(fg_color="#1f538d")
                self.refresh_log_view()
        except queue.Empty:
            pass
        self.after(100, self.check_queue)


def _copy_log_selection(self, event=None):
    """Копирует выделенный текст журнала в буфер обмена."""
    try:
        text = self.log_view.get("sel.first", "sel.last")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
    except Exception:
        pass  # ничего не выделено — молча игнорируем
    return "break"  # событие обработано, дальше не передаём


def _select_all_log(self, event=None):
    """Выделяет весь текст журнала (Ctrl+A)."""
    self.log_view.tag_add("sel", "1.0", "end-1c")
    return "break"
