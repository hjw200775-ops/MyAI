import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from ai import chat, process_post_reply_tasks, refresh_system_prompt
from emotion import get_emotion
from llm import apply_text_settings, create_provider
from llm.config import LLMConfig
from llm.ollama import OllamaProvider
from media import SUPPORTED_IMAGE_EXTENSIONS, validate_image
from memory import (create_conversation, delete_conversation, delete_memory,
                    get_or_create_current_conversation, list_conversations,
                    load_memories, load_message_records, load_messages,
                    rename_conversation, save_memory)
from relationship import get_relationship
from settings import UserSettings, get_settings_service

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
BASE_DIR = Path(__file__).resolve().parent
AVATAR_PATH = BASE_DIR / "assets" / "character" / "xiaoyou_avatar.png"
AVATAR_DISPLAY_SIZE = (72, 72)

if not AVATAR_PATH.is_file():
    raise FileNotFoundError(f"找不到小悠头像资源：{AVATAR_PATH}")

app = ctk.CTk()
app.title("MyAI v1.5")
app.geometry("940x700")
app.minsize(780, 580)

current_conversation_id = get_or_create_current_conversation()
result_queue = queue.Queue()
background_result_queue = queue.Queue()
request_in_progress = False
selected_image_path = None
preview_ctk_image = None
settings_service = get_settings_service()
current_user_settings = settings_service.load()


def _provider_label(settings):
    return "Ollama 本地" if settings.text_provider == "ollama" else "DeepSeek 云端"


def show_memories():
    window = ctk.CTkToplevel(app)
    window.title("长期记忆管理")
    window.geometry("620x500")
    window.transient(app)
    list_frame = ctk.CTkScrollableFrame(window)
    list_frame.pack(fill="both", expand=True, padx=16, pady=(16, 8))
    names = {"identity":"身份", "interest":"兴趣", "study":"学习", "work":"工作",
             "goal":"目标", "preference":"偏好", "relationship":"关系", "other":"其他"}

    def refresh_list():
        for widget in list_frame.winfo_children():
            widget.destroy()
        rows = load_memories()
        if not rows:
            ctk.CTkLabel(list_frame, text="目前没有长期记忆。").pack(pady=20)
        for memory_id, content, category, _, _ in rows:
            row = ctk.CTkFrame(list_frame)
            row.pack(fill="x", padx=4, pady=5)
            ctk.CTkLabel(row, text=f"[{names.get(category, '其他')}] {content}",
                         anchor="w", wraplength=430).pack(side="left", fill="x", expand=True, padx=10, pady=8)
            def remove(mid=memory_id):
                if delete_memory(mid):
                    refresh_system_prompt()
                    refresh_list()
            ctk.CTkButton(row, text="删除", width=58, fg_color="#b33a3a",
                          command=remove).pack(side="right", padx=8, pady=8)

    add_frame = ctk.CTkFrame(window)
    add_frame.pack(fill="x", padx=16, pady=(0, 16))
    entry = ctk.CTkEntry(add_frame, placeholder_text="手动添加一条长期记忆...")
    entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
    def add():
        if save_memory(entry.get(), "other"):
            entry.delete(0, "end")
            refresh_system_prompt()
            refresh_list()
    ctk.CTkButton(add_frame, text="添加", width=70, command=add).pack(side="right", padx=(0, 10), pady=10)
    entry.bind("<Return>", lambda _event: add())
    refresh_list()


def _show_state_window(title, rows):
    window = ctk.CTkToplevel(app)
    window.title(title)
    window.geometry("430x330")
    window.transient(app)
    ctk.CTkLabel(window, text=title, font=("Microsoft YaHei", 20, "bold")).pack(pady=(20, 12))
    for label, value in rows:
        frame = ctk.CTkFrame(window)
        frame.pack(fill="x", padx=24, pady=5)
        ctk.CTkLabel(frame, text=label, width=90, anchor="w").pack(side="left", padx=10, pady=8)
        bar = ctk.CTkProgressBar(frame)
        bar.pack(side="left", fill="x", expand=True, padx=8)
        bar.set(float(value) / 100)
        ctk.CTkLabel(frame, text=f"{value:.1f}", width=48).pack(side="right", padx=8)


def show_emotion():
    state = get_emotion()
    _show_state_window("当前情绪（调试）", [("开心", state["happiness"]),
                                         ("难过", state["sadness"]), ("生气", state["anger"])])


def show_relationship():
    state = get_relationship()
    labels = {"new": "刚认识", "familiar": "熟悉", "close": "亲近"}
    window = ctk.CTkToplevel(app)
    window.title("关系状态（调试）")
    window.geometry("430x370")
    window.transient(app)
    ctk.CTkLabel(window, text=f"当前阶段：{labels[state['stage']]} ({state['stage']})",
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


def show_ai_settings():
    window = ctk.CTkToplevel(app)
    window.title("AI 设置")
    window.geometry("520x460")
    window.resizable(False, False)
    window.transient(app)
    window.grab_set()

    settings = settings_service.load()
    labels = {"DeepSeek 云端": "deepseek", "Ollama 本地": "ollama"}
    selected_label = ctk.StringVar(value=_provider_label(settings))

    ctk.CTkLabel(window, text="AI 设置",
                 font=("Microsoft YaHei", 22, "bold")).pack(pady=(22, 16))
    form = ctk.CTkFrame(window)
    form.pack(fill="x", padx=24, pady=(0, 12))
    ctk.CTkLabel(form, text="文字模型", width=110, anchor="w").grid(
        row=0, column=0, padx=(16, 8), pady=(18, 10), sticky="w")
    provider_menu = ctk.CTkOptionMenu(
        form, values=list(labels), variable=selected_label, width=280)
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
        return UserSettings(
            text_provider=labels[selected_label.get()],
            ollama_model=model_entry.get().strip(),
            ollama_base_url=url_entry.get().strip(),
        )

    def update_ollama_controls(_choice=None):
        state = "normal" if labels[selected_label.get()] == "ollama" else "disabled"
        model_entry.configure(state=state)
        url_entry.configure(state=state)
        check_button.configure(state=state)
        if state == "disabled":
            status_label.configure(text="当前文字 Provider：DeepSeek 云端")
        else:
            status_label.configure(text="可检查 Ollama 服务与模型是否可用。")

    def check_connection():
        draft = draft_settings()
        check_button.configure(state="disabled", text="检查中...")
        status_label.configure(text="正在检查 Ollama...")

        def worker():
            try:
                provider = create_provider(LLMConfig.from_settings(draft))
                if not isinstance(provider, OllamaProvider):
                    raise ValueError("请先选择 Ollama 本地。")
                status = provider.check_status()
                text = status.message
            except Exception:
                text = "检查失败：请确认模型名和 Base URL。"

            def finish():
                check_button.configure(state="normal", text="检查连接")
                status_label.configure(text=text)
            app.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def save_settings():
        global current_user_settings
        try:
            saved = settings_service.save(draft_settings())
            apply_text_settings(saved)
        except (OSError, ValueError) as exc:
            messagebox.showerror("无法保存设置", str(exc), parent=window)
            return
        current_user_settings = saved
        ai_settings_button.configure(text=f"AI 设置 · {_provider_label(saved)}")
        messagebox.showinfo(
            "设置已保存",
            "新的文字 Provider 将从下一条纯文本消息开始生效。\n"
            "图片仍由 DeepSeek Vision 处理。",
            parent=window,
        )
        window.destroy()

    provider_menu.configure(command=update_ollama_controls)
    actions = ctk.CTkFrame(window, fg_color="transparent")
    actions.pack(fill="x", padx=24, pady=(4, 18))
    check_button = ctk.CTkButton(actions, text="检查连接", width=110,
                                 command=check_connection)
    check_button.pack(side="left", padx=5)
    ctk.CTkButton(actions, text="取消", width=90, fg_color="gray35",
                  command=window.destroy).pack(side="right", padx=5)
    ctk.CTkButton(actions, text="保存", width=90,
                  command=save_settings).pack(side="right", padx=5)
    update_ollama_controls()


root_frame = ctk.CTkFrame(app, fg_color="transparent")
root_frame.pack(fill="both", expand=True, padx=14, pady=14)
sidebar = ctk.CTkFrame(root_frame, width=230)
sidebar.pack(side="left", fill="y", padx=(0, 12))
sidebar.pack_propagate(False)
ctk.CTkLabel(sidebar, text="会话", font=("Microsoft YaHei", 20, "bold")).pack(pady=(16, 10))
new_button = ctk.CTkButton(sidebar, text="＋ 新建对话")
new_button.pack(fill="x", padx=12, pady=(0, 10))
conversation_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
conversation_list.pack(fill="both", expand=True, padx=6, pady=(0, 8))

main_frame = ctk.CTkFrame(root_frame)
main_frame.pack(side="left", fill="both", expand=True)
avatar_source = Image.open(AVATAR_PATH)
avatar_image = ctk.CTkImage(
    light_image=avatar_source,
    dark_image=avatar_source,
    size=AVATAR_DISPLAY_SIZE,
)
profile_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
profile_frame.pack(pady=(14, 7))
ctk.CTkLabel(profile_frame, text="", image=avatar_image).pack(side="left", padx=(0, 12))
ctk.CTkLabel(profile_frame, text="小悠", font=("Microsoft YaHei", 24, "bold")).pack(side="left")
button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
button_frame.pack(pady=(0, 8))
ctk.CTkButton(button_frame, text="管理记忆", width=105, command=show_memories).pack(side="left", padx=5)
ctk.CTkButton(button_frame, text="情绪状态", width=105, command=show_emotion).pack(side="left", padx=5)
ctk.CTkButton(button_frame, text="关系状态", width=105, command=show_relationship).pack(side="left", padx=5)
ai_settings_button = ctk.CTkButton(
    button_frame, text=f"AI 设置 · {_provider_label(current_user_settings)}",
    width=145, command=show_ai_settings)
ai_settings_button.pack(side="left", padx=5)
chat_box = ctk.CTkTextbox(main_frame, font=("Microsoft YaHei", 16))
chat_box.pack(fill="both", expand=True, padx=16, pady=(2, 10))
preview_frame = ctk.CTkFrame(main_frame)
preview_image_label = ctk.CTkLabel(preview_frame, text="")
preview_image_label.pack(side="left", padx=10, pady=8)
preview_name_label = ctk.CTkLabel(preview_frame, text="", anchor="w")
preview_name_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
input_frame = ctk.CTkFrame(main_frame)
input_frame.pack(fill="x", padx=16, pady=(0, 14))
attachment_button = ctk.CTkButton(input_frame, text="📎", width=44)
attachment_button.pack(side="left", padx=(10, 0), pady=10)
input_box = ctk.CTkEntry(input_frame, placeholder_text="输入消息...", font=("Microsoft YaHei", 16))
input_box.pack(side="left", fill="x", expand=True, padx=10, pady=10)


def clear_selected_image():
    global selected_image_path, preview_ctk_image
    selected_image_path = None
    # 先让 Tk 标签解除对图片的引用，再释放 Python 侧 CTkImage。
    # 反过来会使底层 pyimage 提前销毁并触发 TclError。
    preview_image_label.configure(image=None, text="")
    preview_ctk_image = None
    preview_name_label.configure(text="")
    preview_frame.pack_forget()


def select_image():
    global selected_image_path, preview_ctk_image
    patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_IMAGE_EXTENSIONS))
    value = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("图片文件", patterns), ("所有文件", "*.*")],
        parent=app,
    )
    if not value:
        return
    try:
        path = validate_image(value)
        with Image.open(path) as source:
            image = source.copy()
        image.thumbnail((180, 120), Image.Resampling.LANCZOS)
        preview_ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
    except (OSError, ValueError) as exc:
        messagebox.showerror("无法选择图片", str(exc), parent=app)
        return
    selected_image_path = str(path)
    preview_image_label.configure(image=preview_ctk_image, text="")
    preview_name_label.configure(text=f"已选择：{path.name}")
    preview_frame.pack(fill="x", padx=16, pady=(0, 8), before=input_frame)


def render_current_conversation():
    chat_box.configure(state="normal")
    chat_box.delete("1.0", "end")
    history = load_message_records(current_conversation_id)
    if history:
        for row in history:
            prefix = "你" if row["role"] == "user" else "小悠"
            image_line = f"[图片：{row['image_path']}]\n" if row["image_path"] else ""
            chat_box.insert("end", f"{prefix}：{image_line}{row['content']}\n\n")
    else:
        chat_box.insert("end", "小悠：你好呀。\n\n")
    chat_box.configure(state="disabled")
    chat_box.see("end")


def switch_conversation(conversation_id):
    global current_conversation_id
    current_conversation_id = int(conversation_id)
    clear_selected_image()
    render_current_conversation()
    refresh_conversation_list()


def rename_dialog(conversation_id):
    title = ctk.CTkInputDialog(text="请输入新的会话标题：", title="重命名会话").get_input()
    if title is not None and rename_conversation(conversation_id, title):
        refresh_conversation_list()


def remove_conversation(conversation_id, title):
    global current_conversation_id
    if not messagebox.askyesno("删除会话", f"确定删除“{title}”吗？\n聊天记录将一起删除。", parent=app):
        return
    was_current = int(conversation_id) == current_conversation_id
    if delete_conversation(conversation_id) and was_current:
        remaining = list_conversations()
        current_conversation_id = remaining[0][0] if remaining else create_conversation()
        render_current_conversation()
    refresh_conversation_list()


def refresh_conversation_list():
    for widget in conversation_list.winfo_children():
        widget.destroy()
    for conversation_id, title, _, _ in list_conversations():
        selected = conversation_id == current_conversation_id
        row = ctk.CTkFrame(conversation_list,
                           fg_color=("gray75", "gray28") if selected else "transparent")
        row.pack(fill="x", pady=3)
        ctk.CTkButton(row, text=title, anchor="w", fg_color="transparent",
                      hover_color=("gray70", "gray35"),
                      command=lambda cid=conversation_id: switch_conversation(cid)).pack(
                          side="left", fill="x", expand=True, padx=(2, 0), pady=2)
        ctk.CTkButton(row, text="✎", width=30, fg_color="transparent",
                      hover_color=("gray70", "gray35"),
                      command=lambda cid=conversation_id: rename_dialog(cid)).pack(side="left", padx=1)
        ctk.CTkButton(row, text="×", width=30, fg_color="transparent", hover_color="#8b3030",
                      command=lambda cid=conversation_id, value=title:
                      remove_conversation(cid, value)).pack(side="right", padx=(0, 2))


def new_conversation():
    switch_conversation(create_conversation("新对话"))
    input_box.focus()


def set_input_enabled(enabled):
    state = "normal" if enabled else "disabled"
    send_button.configure(state=state)
    attachment_button.configure(state=state)
    input_box.configure(state=state)
    if enabled:
        input_box.focus()


def ask_ai(user_text, image_path, conversation_id):
    try:
        ai_reply, saved_memory = chat(user_text, conversation_id, image_path=image_path)
        result_queue.put((conversation_id, ai_reply, saved_memory, None))
        latest = load_message_records(conversation_id, limit=1)
        if (user_text and latest and latest[-1]["role"] == "assistant" and
                latest[-1]["content"] == ai_reply):
            threading.Thread(
                target=run_background_tasks,
                args=(user_text, ai_reply, conversation_id), daemon=True,
            ).start()
    except Exception as exc:
        from llm.diagnostics import report_error
        result_queue.put((conversation_id, "处理消息失败：" + report_error(exc), None, None))


def run_background_tasks(user_text, ai_reply, conversation_id):
    try:
        saved_memory, title = process_post_reply_tasks(
            user_text, ai_reply, conversation_id
        )
    except Exception:
        # Title/memory/state analysis is optional and must not crash this worker.
        saved_memory, title = None, None
    background_result_queue.put((conversation_id, saved_memory, title))


def show_ai_reply(conversation_id, ai_reply, saved_memory, _generated_title):
    global request_in_progress
    request_in_progress = False
    if conversation_id == current_conversation_id:
        history = load_messages(conversation_id)
        render_current_conversation()
        if not history or history[-1][2] != "assistant":
            chat_box.configure(state="normal")
            chat_box.insert("end", f"小悠：{ai_reply}\n\n")
            chat_box.configure(state="disabled")
        if saved_memory:
            chat_box.configure(state="normal")
            chat_box.insert("end", f"[已记住或更新：{saved_memory}]\n\n")
            chat_box.configure(state="disabled")
        chat_box.see("end")
    refresh_conversation_list()
    set_input_enabled(True)


def show_background_result(conversation_id, saved_memory, generated_title):
    if saved_memory and conversation_id == current_conversation_id:
        chat_box.configure(state="normal")
        chat_box.insert("end", f"[已记住或更新：{saved_memory}]\n\n")
        chat_box.configure(state="disabled")
        chat_box.see("end")
    if generated_title:
        refresh_conversation_list()


def process_results():
    try:
        while True:
            show_ai_reply(*result_queue.get_nowait())
    except queue.Empty:
        pass
    try:
        while True:
            show_background_result(*background_result_queue.get_nowait())
    except queue.Empty:
        pass
    app.after(50, process_results)


def send_message():
    global request_in_progress
    user_text = input_box.get().strip()
    image_path = selected_image_path
    if (not user_text and not image_path) or request_in_progress:
        return
    conversation_id = current_conversation_id
    request_in_progress = True
    chat_box.configure(state="normal")
    pending_image = f"[图片：{Path(image_path).name}]\n" if image_path else ""
    chat_box.insert("end", f"你：{pending_image}{user_text}\n\n小悠正在思考...\n\n")
    chat_box.configure(state="disabled")
    chat_box.see("end")
    input_box.delete(0, "end")
    clear_selected_image()
    set_input_enabled(False)
    threading.Thread(target=ask_ai, args=(user_text, image_path, conversation_id), daemon=True).start()


new_button.configure(command=new_conversation)
attachment_button.configure(command=select_image)
cancel_image_button = ctk.CTkButton(preview_frame, text="取消", width=62,
                                    fg_color="#8b3030", command=clear_selected_image)
cancel_image_button.pack(side="right", padx=10, pady=8)
send_button = ctk.CTkButton(input_frame, text="发送", width=80, command=send_message)
send_button.pack(side="right", padx=(0, 10), pady=10)
input_box.bind("<Return>", lambda _event: send_message())
refresh_conversation_list()
render_current_conversation()
input_box.focus()
app.after(50, process_results)
app.mainloop()
