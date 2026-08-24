import queue
import threading
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from ai import chat, generate_conversation_title, refresh_system_prompt
from emotion import get_emotion
from memory import (create_conversation, delete_conversation, delete_memory,
                    get_or_create_current_conversation, list_conversations,
                    load_memories, load_messages, rename_conversation, save_memory)
from relationship import get_relationship

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
BASE_DIR = Path(__file__).resolve().parent
AVATAR_PATH = BASE_DIR / "assets" / "character" / "xiaoyou_avatar.png"
AVATAR_DISPLAY_SIZE = (72, 72)

if not AVATAR_PATH.is_file():
    raise FileNotFoundError(f"找不到小悠头像资源：{AVATAR_PATH}")

app = ctk.CTk()
app.title("MyAI v1.1.4")
app.geometry("940x700")
app.minsize(780, 580)

current_conversation_id = get_or_create_current_conversation()
result_queue = queue.Queue()
request_in_progress = False


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
chat_box = ctk.CTkTextbox(main_frame, font=("Microsoft YaHei", 16))
chat_box.pack(fill="both", expand=True, padx=16, pady=(2, 10))
input_frame = ctk.CTkFrame(main_frame)
input_frame.pack(fill="x", padx=16, pady=(0, 14))
input_box = ctk.CTkEntry(input_frame, placeholder_text="输入消息...", font=("Microsoft YaHei", 16))
input_box.pack(side="left", fill="x", expand=True, padx=10, pady=10)


def render_current_conversation():
    chat_box.configure(state="normal")
    chat_box.delete("1.0", "end")
    history = load_messages(current_conversation_id)
    if history:
        for _, _, role, content, _ in history:
            chat_box.insert("end", f"{'你' if role == 'user' else '小悠'}：{content}\n\n")
    else:
        chat_box.insert("end", "小悠：你好呀。\n\n")
    chat_box.configure(state="disabled")
    chat_box.see("end")


def switch_conversation(conversation_id):
    global current_conversation_id
    current_conversation_id = int(conversation_id)
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
    input_box.configure(state=state)
    if enabled:
        input_box.focus()


def ask_ai(user_text, conversation_id):
    try:
        ai_reply, saved_memory = chat(user_text, conversation_id)
        title = generate_conversation_title(conversation_id)
        result_queue.put((conversation_id, ai_reply, saved_memory, title))
    except Exception:
        result_queue.put((conversation_id, "处理消息时发生错误，请稍后再试。", None, None))


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


def process_results():
    try:
        while True:
            show_ai_reply(*result_queue.get_nowait())
    except queue.Empty:
        pass
    app.after(50, process_results)


def send_message():
    global request_in_progress
    user_text = input_box.get().strip()
    if not user_text or request_in_progress:
        return
    conversation_id = current_conversation_id
    request_in_progress = True
    chat_box.configure(state="normal")
    chat_box.insert("end", f"你：{user_text}\n\n小悠正在思考...\n\n")
    chat_box.configure(state="disabled")
    chat_box.see("end")
    input_box.delete(0, "end")
    set_input_enabled(False)
    threading.Thread(target=ask_ai, args=(user_text, conversation_id), daemon=True).start()


new_button.configure(command=new_conversation)
send_button = ctk.CTkButton(input_frame, text="发送", width=80, command=send_message)
send_button.pack(side="right", padx=(0, 10), pady=10)
input_box.bind("<Return>", lambda _event: send_message())
refresh_conversation_list()
render_current_conversation()
input_box.focus()
app.after(50, process_results)
app.mainloop()
