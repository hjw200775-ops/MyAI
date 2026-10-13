# MyAI

一个正在成长的桌面 AI Companion。

角色：**小悠（Xiaoyou）**

MyAI 不是简单的聊天机器人。它尝试构建一个具备长期记忆、角色状态、情绪与关系模型、图片理解、多模型支持，以及主动陪伴基础架构的个人 AI 助手。

> 当前版本：**V1.6.1 — Companion Foundation Update**

---

## Features

### Intelligent Conversation

- DeepSeek API
- Ollama Local Model
- Multi Provider — 文字 Provider 可在 DeepSeek 云端与 Ollama 本地之间动态切换
- 多轮上下文对话

### Memory

- Long-term memory（用户信息记录）
- Memory management（记忆管理界面，支持增删改）
- System Prompt 自动刷新

### Character System

- Emotion state（情绪状态）
- Relationship state（关系状态）

### Vision

- Image understanding（图片上传、分析、消息展示）
- 独立的 DeepSeek Vision 路线，不随文字 Provider 切换

### Companion Core

- `CompanionState`
- Time Awareness（时间感知基础）
- Proactive Decision（主动行为决策基础）
- Event System（`EventLog`）

### Desktop Experience

- CustomTkinter GUI
- Message Bubble
- Input Panel
- Sidebar 导航
- Memory 页面 / Settings 页面
- Dark / Light Theme

---

## Architecture

```text
UI
 ↓
Controller
 ↓
Core / Services
 ↓
LLM Provider
```

对应到代码：

```text
ui/                     界面层：MainWindow / Sidebar / TitleBar / ChatPage / MessageBubble
 ↓
ui/controller.py        ChatController：串接界面与业务
 ↓
core/ · ai.py · memory.py · settings.py
                        核心与服务：CompanionState / TimeAwareness / Proactive / EventLog，
                        对话流程、长期记忆、用户偏好
 ↓
llm/                    Provider：DeepSeek / Ollama / DeepSeek Vision
```

`gui.py` 是唯一入口，只负责启动 `ui.app.run()`。界面实现全部位于 `ui/` 包，业务逻辑通过 `ChatController` 调用 `core/`、`ai`、`memory`、`llm`、`settings`。

---

## Project Structure

```text
MyAI-Companion
├── core/                   Companion 核心
│   ├── companion_state.py
│   ├── time_awareness.py
│   ├── proactive.py
│   └── events.py
│
├── ui/                     界面层
│   ├── app.py              应用启动
│   ├── controller.py       ChatController
│   ├── main_window.py
│   ├── chat_view.py
│   ├── message_bubble.py
│   ├── input_panel.py
│   ├── model_selector.py
│   ├── pages.py            Memory / Settings 页面
│   ├── sidebar.py
│   ├── titlebar.py
│   └── theme.py
│
├── llm/                    Provider 层
│   ├── base.py
│   ├── deepseek.py
│   ├── ollama.py
│   ├── deepseek_vision.py
│   └── openai_vision.py
│
├── tests/                  离线测试（模拟 Provider，不发真实请求）
├── docs/                   设计文档
├── assets/                 资源（角色立绘等）
│
├── ai.py                   对话流程
├── memory.py               长期记忆
├── settings.py             用户偏好持久化
└── gui.py                  入口
```

---

## Requirements

- Windows 10 / 11
- Python 3.10+
- CustomTkinter

```bash
pip install -r requirements.txt
```

---

## Configuration

复制示例配置并填入自己的 API Key：

```bash
cp .env.example .env
```

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

`.env` 已被 `.gitignore` 排除，**请勿提交到公开仓库**。

如需使用 Ollama，请先安装并启动 Ollama，并准备一个本地模型，默认服务地址为 `http://127.0.0.1:11434`。

---

## Run

```bash
python gui.py
```

---

## Tests

测试全部使用模拟 Provider / HTTP，不需要真实的 DeepSeek 或 Ollama 服务，也不会发送真实 API 请求。部分测试需要隔离入口（临时数据库、屏蔽网络）：

```bash
python -m compileall -q .
python tests/run_offline.py tests/foundations_test.py
```

---

## Roadmap

| Version | Theme |
| --- | --- |
| **V1.6.1** | Companion Foundation |
| **V1.6.2** | Proactive Companion |
| **V1.7** | Desktop Companion |
| **V2.0** | Multimodal AI Companion |

- **V1.6.1 — Companion Foundation**（当前）：GUI 组件化重构、Companion Core 基础、Memory / Settings 页面、时间感知与主动行为决策基础。
- **V1.6.2 — Proactive Companion**：Companion Loop、用户活动感知、主动消息规划优化。
- **V1.7 — Desktop Companion**：Live2D 集成、状态表现、桌宠模式。
- **V2.0 — Multimodal AI Companion**：多模态理解、语音交互、更完整的人格成长系统。

---

## License

本项目目前用于学习、研究与个人开发。
