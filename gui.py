"""MyAI 桌面入口。

    python gui.py

界面实现位于 ui/ 包（MainWindow / Sidebar / TitleBar / ChatPage ...），
业务逻辑经 ui.controller.ChatController 调用 ai / memory / llm / settings。
"""
from ui.app import run

if __name__ == "__main__":
    run()
