# MyAI

一个基于大语言模型的个人 AI 聊天助手项目。

> Current version: v1.1.3

## Features

- DeepSeek API 对话
- Python GUI 聊天界面
- 角色人格系统
- 长期记忆系统
- 情绪状态系统
- 关系状态系统
- 本地 SQLite 数据持久化

## Project Structure

```text
MyAI/
├── ai.py
├── character.py
├── emotion.py
├── gui.py
├── memory.py
├── relationship.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Installation

```bash
pip install -r requirements.txt
```

## API Configuration

复制 `.env.example` 为 `.env`，填入自己的 API Key。

真实 API Key 不应提交到 GitHub。

## Privacy

以下文件不会上传：

- .env
- memory.db
- 本地聊天记录
- 虚拟环境

## Roadmap

- 多模态图片理解
- 语音交互
- 更完善的 AI 陪伴系统
- 机器人硬件接口
