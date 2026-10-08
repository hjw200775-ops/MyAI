# MyAI V1.5 — GUI 云端 / 本地模型切换

V1.5 在 V1.4.2 稳定代码上增加“AI 设置”：无需修改 `.env` 或重启，即可让后续纯文字消息在 DeepSeek 云端与 Ollama 本地之间切换。DeepSeek Vision、图片上传、HTTP 400 修复、人格、长期记忆、情绪、关系、会话历史和标题容错保持原路线。

## V1.5 新功能

- 主界面新增“AI 设置”，并显示当前文字 Provider。
- 选择 DeepSeek 云端或 Ollama 本地，保存后从下一条纯文字消息开始生效。
- 可编辑 Ollama 模型名和 Base URL，并检查服务、连接和模型安装状态。
- 非敏感偏好写入用户 `settings.json`；API Key 永远不进入该文件。
- 配置文件缺失、损坏或字段不完整时安全回退到 `.env` / 内置默认值。
- 设置采用同目录临时文件加原子替换，降低写入中断造成 JSON 损坏的风险。
- 图片理解始终使用独立的 DeepSeek Vision，不跟随文字 Provider 切换。

## 安装与运行

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python gui.py
```

在本机 `.env` 中填写自己的 `DEEPSEEK_API_KEY`。不要上传、截图或提交 `.env`。

如需使用 Ollama，请先安装并启动 Ollama，再准备一个本地模型，例如：

```powershell
ollama run qwen3.5:2b
```

退出模型交互后保持 Ollama 后台服务运行。默认服务地址为 `http://127.0.0.1:11434`。

## AI 设置使用方法

1. 点击主界面的“AI 设置”。
2. 在“文字模型”中选择“DeepSeek 云端”或“Ollama 本地”。
3. 使用 Ollama 时填写已安装的模型名和服务根地址；Base URL 不要追加 `/api/chat`。
4. 可点击“检查连接”，区分服务未启动/无法连接、超时、响应异常和模型未安装。
5. 点击“保存”。新选择从下一条纯文字消息开始生效，无需重启。

切换只影响文字生成以及使用文字 Provider 的标题、记忆、情绪和关系后台分析。它们继续复用同一个 `ContextBuilder`，因此人格、长期记忆、情绪、关系和最近聊天上下文不会丢失。当前或历史上下文中含图片时，请求仍交给 DeepSeek Vision。

## `.env` 与 `settings.json`

`.env` 负责敏感信息和高级/首次运行默认值：

```env
DEEPSEEK_API_KEY=你的_DeepSeek_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
MYAI_LLM_TIMEOUT=30

TEXT_PROVIDER=deepseek
OLLAMA_MODEL=qwen3.5:2b
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_TIMEOUT=60
OLLAMA_KEEP_ALIVE=10m
OLLAMA_NUM_CTX=4096
OLLAMA_THINK=false

MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
MYAI_VISION_TIMEOUT=120
```

首次没有用户设置文件时，`TEXT_PROVIDER`、`OLLAMA_MODEL` 和 `OLLAMA_BASE_URL` 会作为初始值。用户在 GUI 保存后，以下非敏感偏好写入：

```text
%APPDATA%\MyAI\settings.json
```

文件内容示例：

```json
{
  "text_provider": "ollama",
  "ollama_model": "qwen3.5:2b",
  "ollama_base_url": "http://127.0.0.1:11434"
}
```

`settings.json` 不保存 DeepSeek API Key、超时、聊天、记忆或图片。删除它会恢复 `.env` / 内置默认值；损坏 JSON 也不会阻止程序启动。

## 数据与升级安全

默认数据库和托管图片位置保持 V1.4.2 规则不变。升级原项目时先备份，然后覆盖源码，但保留自己的 `.env`、`memory.db` 和 `%LOCALAPPDATA%\MyAI\images`（或自定义 `MYAI_DATA_DIR`）。V1.5 的用户模型偏好位于 `%APPDATA%\MyAI\settings.json`。

交付包不包含 `.env`、API Key、虚拟环境、数据库、聊天记录、缓存或私人运行时图片。错误信息继续使用安全分类，不输出远端原始正文、请求头、对话、base64 图片或 API Key。

## 项目结构

```text
gui.py                  现有 GUI；新增轻量 AI 设置窗口
settings.py             非敏感用户偏好的容错与原子持久化
ai.py                   聊天流程；按内容选择文字/Vision Provider
context.py              人格、情绪、关系、记忆和历史上下文
llm/
  base.py               Provider 统一接口
  config.py             env 与用户偏好合并
  deepseek.py           DeepSeek 纯文字 Provider
  ollama.py             Ollama 纯文字 Provider 与连接检查
  deepseek_vision.py    固定 DeepSeek Vision 路线
tests/
  settings_test.py      V1.5 设置与热切换离线测试
  smoke_test.py
  vision_regression_test.py
  ollama_provider_test.py
  latency_regression_test.py
  title_resilience_test.py
```

## 离线检查

```powershell
python -m compileall -q .
python tests\deepseek_provider_test.py
python tests\latency_regression_test.py
python tests\ollama_provider_test.py
python tests\settings_test.py
python tests\smoke_test.py
python tests\title_resilience_test.py
python tests\vision_regression_test.py
```

测试全部使用模拟 Provider/HTTP，不需要真实 DeepSeek/Ollama 服务，也不会发送真实 API 请求。

## V1.5 本地验收

1. 安装依赖并运行全部离线检查。
2. 启动 GUI，确认标题为 MyAI v1.5，且“AI 设置”显示当前文字 Provider。
3. 选择 DeepSeek，发送纯文字，确认原 `deepseek-flash` 路线正常。
4. 选择 Ollama，填写本机模型与 Base URL，点击“检查连接”，保存后不重启直接发送下一条纯文字。
5. 在两个 Provider 间往返切换，确认每次保存后下一条纯文字立即使用新选择。
6. 确认人格、长期记忆、情绪、关系、会话历史和自动标题仍正常。
7. 在 Ollama 文字模式上传图片并追问历史图片，确认图片仍由 DeepSeek Vision 理解。
8. 分别停止 Ollama、填写不存在的模型，确认状态提示可区分连接问题和模型缺失，GUI 不冻结。
9. 查看 `%APPDATA%\MyAI\settings.json`，确认仅有三个非敏感字段，没有 API Key。
10. 临时破坏或删除 settings 文件，重新启动，确认程序用安全默认值正常打开。

真实 API 权限、网络、模型速度和 GUI 点击流程需在用户机器上完成。验证稳定前不要发布或提交 GitHub。
