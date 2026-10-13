"""MyAI「小悠」桌面 UI 包。

分层约定（见 docs/UI_DESIGN.md）：

    ui.theme        Design Token（颜色 / 圆角 / 间距 / 字体 / 动效），纯数据，不依赖 tkinter
    ui.ui_prefs     独立的 UI 偏好持久化（外观模式等），不触碰 settings.py
    ui.models       UI 层消息模型（MessageKind：USER / ASSISTANT / PROACTIVE / SYSTEM）
    ui.controller   ChatController：聊天 / 会话 / 记忆 / 设置的非 UI 逻辑与后台线程调度
    ui.assets       头像等静态资源加载（PIL 层，可选 CTkImage 包装）
    ui.icons        PIL 绘制的单色线性图标
    ui.platform_win Windows DWM 标题栏染色（方案 A，不用 overrideredirect）

    ui.widgets      Card / PageHeader / IconButton / NavButton / StatusIndicator
    ui.titlebar     窗口内部视觉标题区
    ui.sidebar      72px 图标导航 + 小悠状态
    ui.chat_history 最近 N 条分页窗口（纯 Python，不依赖 tkinter）
    ui.message_bubble  USER / ASSISTANT / PROACTIVE / SYSTEM 气泡
    ui.input_panel  多行输入、图片预览、发送
    ui.chat_view    对话页（可折叠会话列 + 气泡聊天区）
    ui.model_selector  聊天页 Provider 快捷切换
    ui.pages        记忆 / 视觉 / 设置 页面
    ui.dialogs      原有四个弹窗（主界面不再打开）
    ui.main_window  MainWindow：布局、页面切换、主线程轮询分发
    ui.app          create_app() / run()

业务模块（ai / memory / llm / settings / media ...）不得反向 import 本包。
"""
