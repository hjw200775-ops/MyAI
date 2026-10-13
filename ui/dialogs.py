"""V1.6.1 原有的四个弹窗（记忆管理 / 情绪 / 关系 / AI 设置）。

主界面不再打开它们：记忆、模型和角色状态都在页面里。
这里先留着，Phase 9 再决定是否删除。
"""
from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from .controller import PROVIDER_LABELS, ChatController
from .models import ConnectionCheckEvent

ConnectionListener = Callable[[ConnectionCheckEvent], None]


def show_memories(master, controller: ChatController) -> ctk.CTkToplevel:
    window = ctk.CTkToplevel(master)
    window.title("长期记忆管理")
    window.geometry("620x500")
    window.transient(master)
    list_frame = ctk.CTkScrollableFrame(window)
    list_frame.pack(fill="both", expand=True, padx=16, pady=(16, 8))

    def refresh_list():
        for widget in list_frame.winfo_children():
            widget.destroy()
        rows = controller.memories()
        if not rows:
            ctk.CTkLabel(list_frame, text="目前没有长期记忆。").pack(pady=20)
        for item in rows:
            row = ctk.CTkFrame(list_frame)
            row.pack(fill="x", padx=4, pady=5)
            ctk.CTkLabel(row, text=f"[{item.category_label}] {item.content}",
                         anchor="w", wraplength=430).pack(side="left", fill="x", expand=True, padx=10, pady=8)
            def remove(mid=item.id):
                if controller.delete_memory(mid):
                    refresh_list()
            ctk.CTkButton(row, text="删除", width=58, fg_color="#b33a3a",
                          command=remove).pack(side="right", padx=8, pady=8)

    add_frame = ctk.CTkFrame(window)
    add_frame.pack(fill="x", padx=16, pady=(0, 16))
    entry = ctk.CTkEntry(add_frame, placeholder_text="手动添加一条长期记忆...")
    entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
    def add():
        if controller.add_memory(entry.get(), "other"):
            entry.delete(0, "end")
            refresh_list()
    ctk.CTkButton(add_frame, text="添加", width=70, command=add).pack(side="right", padx=(0, 10), pady=10)
    entry.bind("<Return>", lambda _event: add())
    refresh_list()
    return window


def _show_state_window(master, title, rows):
    window = ctk.CTkToplevel(master)
    window.title(title)
    window.geometry("430x330")
    window.transient(master)
    ctk.CTkLabel(window, text=title, font=("Microsoft YaHei", 20, "bold")).pack(pady=(20, 12))
    for label, value in rows:
        frame = ctk.CTkFrame(window)
        frame.pack(fill="x", padx=24, pady=5)
        ctk.CTkLabel(frame, text=label, width=90, anchor="w").pack(side="left", padx=10, pady=8)
        bar = ctk.CTkProgressBar(frame)
        bar.pack(side="left", fill="x", expand=True, padx=8)
        bar.set(float(value) / 100)
        ctk.CTkLabel(frame, text=f"{value:.1f}", width=48).pack(side="right", padx=8)
    return window


def show_emotion(master, controller: ChatController):
    state = controller.emotion_state()
    return _show_state_window(master, "当前情绪（调试）", [("开心", state["happiness"]),
                                                         ("难过", state["sadness"]), ("生气", state["anger"])])


def show_relationship(master, controller: ChatController):
    state = controller.relationship_state()
    window = ctk.CTkToplevel(master)
    window.title("关系状态（调试）")
    window.geometry("430x370")
    window.transient(master)
    ctk.CTkLabel(window, text=f"当前阶段：{state['stage_label']} ({state['stage']})",
                 font=("Microsoft YaHei", 18, "bold")).pack(pady=(22, 12))
    for label, key in (("信任", "trust"), ("熟悉", "familiarity"), ("亲近", "closeness")):
        frame = ctk.CTkFrame(window)
        frame.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(frame, text=label, width=70).pack(side="left", padx=10, pady=10)
        bar = ctk.CTkProgressBar(frame)
        bar.pack(side="left", fill="x", expand=True, padx=8)
        bar.set(state[key] / 100)
        ctk.CTkLabel(frame, text=f"{state[key]:.1f}", width=48).pack(side="right", padx=8)
    ctk.CTkLabel(window, text="这些数值仅用于调试，不会插入聊天记录。",
                 text_color="gray70").pack(pady=14)
    return window


def show_ai_settings(master, controller: ChatController, *,
                     add_listener: Callable[[ConnectionListener], None],
                     remove_listener: Callable[[ConnectionListener], None],
                     on_saved: Callable[[], None] | None = None):
    window = ctk.CTkToplevel(master)
    window.title("AI 设置")
    window.geometry("520x460")
    window.resizable(False, False)
    window.transient(master)
    window.grab_set()

    settings = controller.user_settings
    selected_label = ctk.StringVar(value=controller.provider_label)

    ctk.CTkLabel(window, text="AI 设置",
                 font=("Microsoft YaHei", 22, "bold")).pack(pady=(22, 16))
    form = ctk.CTkFrame(window)
    form.pack(fill="x", padx=24, pady=(0, 12))
    ctk.CTkLabel(form, text="文字模型", width=110, anchor="w").grid(
        row=0, column=0, padx=(16, 8), pady=(18, 10), sticky="w")
    provider_menu = ctk.CTkOptionMenu(
        form, values=list(PROVIDER_LABELS.values()), variable=selected_label, width=280)
    provider_menu.grid(row=0, column=1, padx=(8, 16), pady=(18, 10), sticky="ew")

    ctk.CTkLabel(form, text="Ollama 模型", width=110, anchor="w").grid(
        row=1, column=0, padx=(16, 8), pady=10, sticky="w")
    model_entry = ctk.CTkEntry(form, width=280)
    model_entry.insert(0, settings.ollama_model)
    model_entry.grid(row=1, column=1, padx=(8, 16), pady=10, sticky="ew")

    ctk.CTkLabel(form, text="Ollama 地址", width=110, anchor="w").grid(
        row=2, column=0, padx=(16, 8), pady=10, sticky="w")
    url_entry = ctk.CTkEntry(form, width=280)
    url_entry.insert(0, settings.ollama_base_url)
    url_entry.grid(row=2, column=1, padx=(8, 16), pady=10, sticky="ew")
    form.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        window,
        text="图片理解固定使用 DeepSeek Vision，不随文字模型切换。\n界面不会显示或保存 DeepSeek API Key。",
        text_color="gray70", justify="left",
    ).pack(fill="x", padx=30, pady=(2, 10))
    status_label = ctk.CTkLabel(window, text="", anchor="w")
    status_label.pack(fill="x", padx=30, pady=(0, 8))

    def draft_settings():
        return controller.draft_settings(selected_label.get(), model_entry.get(), url_entry.get())

    def update_ollama_controls(_choice=None):
        state = "normal" if draft_settings().text_provider == "ollama" else "disabled"
        model_entry.configure(state=state)
        url_entry.configure(state=state)
        check_button.configure(state=state)
        if state == "disabled":
            status_label.configure(text="当前文字 Provider：DeepSeek 云端")
        else:
            status_label.configure(text="可检查 Ollama 服务与模型是否可用。")

    def on_connection_result(event: ConnectionCheckEvent):
        if not window.winfo_exists():
            return
        check_button.configure(text="检查连接")
        update_ollama_controls()
        if draft_settings() == event.draft:
            status_label.configure(text=event.message)

    add_listener(on_connection_result)

    def check_connection():
        check_button.configure(state="disabled", text="检查中...")
        status_label.configure(text="正在检查 Ollama...")
        controller.check_connection(draft_settings())

    def on_close():
        remove_listener(on_connection_result)
        window.destroy()

    def save_settings():
        try:
            controller.save_settings(draft_settings())
        except (OSError, ValueError):
            messagebox.showerror("无法保存设置", "设置保存失败，请检查配置内容及目录写入权限。", parent=window)
            return
        if on_saved is not None:
            on_saved()
        messagebox.showinfo(
            "设置已保存",
            "新的文字 Provider 将从下一条纯文本消息开始生效。\n"
            "图片仍由 DeepSeek Vision 处理。",
            parent=window,
        )
        on_close()

    window.protocol("WM_DELETE_WINDOW", on_close)
    provider_menu.configure(command=update_ollama_controls)
    actions = ctk.CTkFrame(window, fg_color="transparent")
    actions.pack(fill="x", padx=24, pady=(4, 18))
    check_button = ctk.CTkButton(actions, text="检查连接", width=110,
                                 command=check_connection)
    check_button.pack(side="left", padx=5)
    ctk.CTkButton(actions, text="取消", width=90, fg_color="gray35",
                  command=on_close).pack(side="right", padx=5)
    ctk.CTkButton(actions, text="保存", width=90,
                  command=save_settings).pack(side="right", padx=5)
    update_ollama_controls()
    return window


__all__ = ["show_memories", "show_emotion", "show_relationship", "show_ai_settings",
           "ConnectionListener"]
