import os
import json
import queue
import customtkinter as ctk

# Очередь для безопасной передачи данных между потоками
gui_queue = queue.Queue()


class PhoenixGUI(ctk.CTk):
    def __init__(self, jarvis_instance, config_path, on_command_cb,
                 on_mic_toggle_cb=None, on_voice_change_cb=None,
                 on_model_change_cb=None):
        super().__init__()
        self.jarvis = jarvis_instance
        self.config_path = config_path
        self.on_command_cb = on_command_cb
        self.on_mic_toggle_cb = on_mic_toggle_cb
        self.on_voice_change_cb = on_voice_change_cb
        self.on_model_change_cb = on_model_change_cb

        self._settings_win = None

        self.title("Phoenix")
        self.resizable(False, False)
        self._center_window(420, 650)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.load_current_config()
        self._build_ui()

        self.after(100, self.check_queue)
        self.after(500, self._sync_mic_state)

    def _center_window(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        top.grid_columnconfigure(1, weight=1)

        self.indicator = ctk.CTkButton(
            top, text="", width=50, height=50, corner_radius=25,
            fg_color="#1f538d", hover_color="#2e7fd6",
            border_width=3, border_color="#00d2ff",
        )
        self.indicator.grid(row=0, column=0, rowspan=2, padx=(0, 12))

        self.status_label = ctk.CTkLabel(
            top, text="Система готова",
            font=("Segoe UI", 14, "bold"),
            text_color="#00d2ff", anchor="w",
        )
        self.status_label.grid(row=0, column=1, sticky="w")

        self.mic_switch = ctk.CTkSwitch(
            top, text="Микрофон", command=self._toggle_mic,
            font=("Segoe UI", 11),
        )
        if getattr(self.jarvis, "listening_enabled", True):
            self.mic_switch.select()
        self.mic_switch.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.settings_btn = ctk.CTkButton(
            top, text="⚙", width=40, height=40, corner_radius=20,
            font=("Segoe UI Emoji", 20),
            fg_color="#2a2d2e", hover_color="#3a3d3e",
            command=self._open_settings,
        )
        self.settings_btn.grid(row=0, column=2, rowspan=2, padx=(8, 0))

        self.chat_log = ctk.CTkTextbox(
            self, font=("Segoe UI", 13), corner_radius=10, wrap="word",
        )
        self.chat_log.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        self.chat_log.insert("0.0", "Феникс активен.\nСлушаю ваши инструкции...\n")
        self.chat_log.configure(state="disabled")

        self.entry = ctk.CTkEntry(
            self, height=45, corner_radius=10,
            placeholder_text="Напишите команду и нажмите Enter...",
        )
        self.entry.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.entry.bind("<Return>", self.send_text_command)

    def load_current_config(self):
        self.current_config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.current_config = json.load(f)
            except Exception:
                self.current_config = {}

    def _open_settings(self):
        if self._settings_win is not None:
            try:
                if self._settings_win.winfo_exists():
                    self._settings_win.lift()
                    self._settings_win.focus()
                    return
            except Exception:
                pass

        win = ctk.CTkToplevel(self)
        win.title("Настройки")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 340) // 2
        y = self.winfo_y() + (self.winfo_height() - 380) // 2
        win.geometry(f"340x380+{x}+{y}")
        win.after(50, win.lift)
        self._settings_win = win

        model_label = ctk.CTkLabel(win, text="Модель ИИ (Ollama):",
                                   font=("Segoe UI", 12, "bold"))
        model_label.pack(anchor="w", padx=15, pady=(15, 5))

        models = self._get_ollama_models()
        current_model = self.current_config.get("llm_model", "qwen2.5:1.5b")
        if current_model not in models:
            models.insert(0, current_model)
        if not models:
            models = [current_model]

        model_menu = ctk.CTkOptionMenu(win, values=models, width=310)
        model_menu.set(current_model)
        model_menu.pack(padx=15, pady=2)

        refresh_btn = ctk.CTkButton(
            win, text="↻ Обновить список моделей",
            command=lambda: self._refresh_models(model_menu),
            fg_color="#444", hover_color="#555", height=26, width=310,
        )
        refresh_btn.pack(padx=15, pady=(4, 10))

        ctk.CTkLabel(win, text="Голос ассистента (TTS):",
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(5, 5))

        voices = self._get_piper_voices()
        current_voice = self.current_config.get("tts_voice", "ruslan")
        if current_voice not in voices:
            voices.insert(0, current_voice)

        voice_menu = ctk.CTkOptionMenu(win, values=voices, width=310)
        voice_menu.set(current_voice)
        voice_menu.pack(padx=15, pady=2)

        whisper_switch = ctk.CTkSwitch(win, text="Включить Whisper")
        if self.current_config.get("use_whisper", False):
            whisper_switch.select()
        whisper_switch.pack(anchor="w", padx=20, pady=15)
        old_model = self.current_config.get("llm_model", "qwen2.5:1.5b")
        old_voice = self.current_config.get("tts_voice", "ruslan")

        def save_and_close():
            new_model = model_menu.get().strip()
            new_voice = voice_menu.get().strip()
            model_changed = (new_model != old_model)
            voice_changed = (new_voice != old_voice)

            self.current_config["llm_model"] = new_model
            self.current_config["tts_voice"] = new_voice
            self.current_config["use_whisper"] = bool(whisper_switch.get())

            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.current_config, f, indent=2, ensure_ascii=False)
                self.status_label.configure(text="Настройки сохранены")
            except Exception as e:
                self.status_label.configure(text=f"Ошибка: {e}")
                return

            self._close_settings()

            if model_changed or voice_changed:
                self._apply_settings_changes(
                    new_model if model_changed else None,
                    new_voice if voice_changed else None,
                )

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="Сохранить", command=save_and_close,
                      fg_color="#2b7337", hover_color="#399648", width=140).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Отмена", command=self._close_settings,
                      fg_color="#444", hover_color="#555", width=140).pack(side="left", padx=5)

        win.protocol("WM_DELETE_WINDOW", self._close_settings)

    def _close_settings(self):
        if self._settings_win is not None:
            try:
                self._settings_win.grab_release()
                self._settings_win.destroy()
            except Exception:
                pass
            self._settings_win = None

    def append_to_log(self, sender, text):
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", f"\n{sender}: {text}")
        self.chat_log.configure(state="disabled")
        self.chat_log.see("end")

    def send_text_command(self, event=None):
        text = self.entry.get().strip()
        if text:
            self.append_to_log("Вы", text)
            self.entry.delete(0, "end")
            self.status_label.configure(text="Феникс думает...")
            self.indicator.configure(
                fg_color="#ff9000",
                border_color="#ff0500"
            )
            self.on_command_cb(text)

    def check_queue(self):
        # Статус и цвет обновляются ТОЛЬКО когда реально пришёл ответ из очереди.
        # Если очередь пуста — ничего не трогаем, чтобы не сбить «Феникс думает...».
        try:
            while True:
                sender, text = gui_queue.get_nowait()
                self.append_to_log(sender, text)
                self.status_label.configure(text="Система готова")
                if self.mic_switch.get():
                    self.indicator.configure(fg_color="#1f538d", border_color="#00d2ff")
                else:
                    self.indicator.configure(fg_color="#333333", border_color="#666666")
        except queue.Empty:
            pass
        self.after(100, self.check_queue)

    def _toggle_mic(self):
        enabled = bool(self.mic_switch.get())
        if self.on_mic_toggle_cb:
            try:
                self.on_mic_toggle_cb(enabled)
            except Exception as e:
                self.status_label.configure(text=f"Ошибка микрофона: {e}")
                return
        if enabled:
            self.status_label.configure(text="Микрофон включён, слушаю...")
            self.indicator.configure(fg_color="#1f538d", border_color="#00d2ff")
        else:
            self.status_label.configure(text="Микрофон выключен")
            self.indicator.configure(fg_color="#333333", border_color="#666666")

    def _sync_mic_state(self):
        core_state = bool(getattr(self.jarvis, "listening_enabled", True))
        if core_state != bool(self.mic_switch.get()):
            if core_state:
                self.mic_switch.select()
                self.status_label.configure(text="Микрофон включён, слушаю...")
                self.indicator.configure(fg_color="#1f538d", border_color="#00d2ff")
            else:
                self.mic_switch.deselect()
                self.status_label.configure(text="Микрофон выключен")
                self.indicator.configure(fg_color="#333333", border_color="#666666")
        self.after(500, self._sync_mic_state)

    def _get_ollama_models(self):
        """Запрашивает у Ollama список установленных моделей."""
        try:
            import urllib.request
            url = self.current_config.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
            with urllib.request.urlopen(url + "/api/tags", timeout=3) as r:
                data = json.loads(r.read())
            return sorted(m["name"] for m in data.get("models", []) if m.get("name"))
        except Exception as e:
            print(f"[settings] Ollama недоступна: {e}")  # для отладки в консоли
            return []

    def _get_piper_voices(self):
        """Известные русские голоса Piper. Список можно расширить."""
        return ["ruslan", "dmitri", "irina", "denis"]

    def _refresh_models(self, model_menu):
        """Перечитывает список моделей из Ollama и обновляет выпадающий список."""
        models = self._get_ollama_models()
        current = model_menu.get()
        if current and current not in models:
            models.insert(0, current)
        if not models:
            self.status_label.configure(text="Ollama недоступна")
            return
        model_menu.configure(values=models)
        model_menu.set(current if current in models else models[0])
        self.status_label.configure(text=f"Найдено моделей: {len(models)}")

    def _apply_settings_changes(self, new_model, new_voice):
        """Применяет новую модель/голос в фоне, показывает прогресс."""
        parts = []
        if new_model: parts.append(f"модель {new_model}")
        if new_voice: parts.append(f"голос {new_voice}")
        self.status_label.configure(text=f"Применяю: {', '.join(parts)}...")
        self.indicator.configure(
            fg_color="#ff9000",
            border_color="#ff0500"
        )

        import threading
        results = {}

        def _worker():
            if new_voice and self.on_voice_change_cb:
                try:
                    results["voice"] = self.on_voice_change_cb(new_voice)
                except Exception:
                    results["voice"] = False
            if new_model and self.on_model_change_cb:
                try:
                    results["model"] = self.on_model_change_cb(new_model)
                except Exception:
                    results["model"] = False

            def _report():
                msgs = []
                if "voice" in results:
                    msgs.append(f"Голос {'установлен' if results['voice'] else 'не установлен'}")
                if "model" in results:
                    msgs.append(f"Модель {'установлена' if results['model'] else 'не установлен'}")
                self.status_label.configure(text=", ".join(msgs) if msgs else "Готово")
                if self.mic_switch.get():
                    self.indicator.configure(fg_color="#1f538d", border_color="#00d2ff")
                else:
                    self.indicator.configure(fg_color="#333333", border_color="#666666")

            self.after(0, _report)

        threading.Thread(target=_worker, daemon=True).start()
