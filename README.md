# MyAI V1.4.2 — 空返回容错修复

V1.4.2 基于 V1.4.1 修复空标题导致 GUI 后台线程触发 `IndexError` 的问题，并增强 Ollama、DeepSeek 文字响应及标题/记忆/关系等辅助任务对空值和异常格式的容错。V1.4.1 的延迟优化、Ollama 纯文字 Provider 与 V1.3.2 的 DeepSeek/Vision 能力全部保留。

## V1.4.2 Bugfix

- `_clean_title()` 安全处理 `None`、空字符串和纯空白，不再对空列表取 `[0]`。
- 模型标题无效时使用清理后的用户首条文本；仍无可用内容时保留项目默认标题“新对话”。
- 后台状态、记忆和标题结果缺字段或格式异常时安全跳过，不让辅助任务异常终止 GUI 工作线程。
- Ollama 与 DeepSeek 文字 Provider 对空回复和异常响应提供明确中文错误。
- 新增完全离线的标题、辅助结果和 Provider 返回格式回归测试。

## V1.4.1 延迟修复

- 正式聊天回复现在是显示前唯一一次模型请求；保存成功后立刻交给 GUI。
- 情绪、关系、长期记忆和标题分析合并成一次请求，在回复显示后由后台线程完成。
- 后台分析超时固定为 15 秒；失败不会撤回或阻塞已经显示的回复。
- Ollama 默认 `think=false`，避免普通陪伴对话生成额外思考内容。
- Ollama 默认保活 10 分钟，减少每条消息重复装载模型的冷启动。
- 本地上下文默认限制为 4096，以降低 8 GB 显存设备的首字延迟和显存压力。
- 速度仍取决于模型、显卡是否启用及对话长度；本版本不承诺固定秒数。

## V1.4 更新

- `llm/ollama.py` 独立实现 Ollama Provider，没有把本地模型逻辑塞进 `ai.py`。
- `TEXT_PROVIDER=deepseek|ollama` 选择文字 Provider；旧的 `MYAI_LLM_PROVIDER` 仍可作为兼容配置。
- Ollama 使用现有 `ContextBuilder` 的完整 messages，因此系统人格、记忆、情绪、关系和最近 30 条聊天仍会进入本地模型。
- 图片路由保持不变：只要上下文含当前或历史图片，就继续调用独立的 DeepSeek Vision Provider，不把图片交给 Ollama。
- 连接失败、超时、模型未安装、返回格式异常和空回复都有中文提示；GUI 继续在后台线程中请求，不阻塞界面。
- 不新增运行依赖，不包含 `.env`、API Key、数据库或历史图片。

## 安装

### 1. 安装 Python 依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 安装并启动 Ollama

Windows 10 22H2 或更新版本可使用 [Ollama 官方 Windows 安装程序](https://ollama.com/download/windows)。安装后 Ollama 通常会在后台运行，并在 `http://localhost:11434` 提供本地 API。官方说明见 [Ollama Windows 文档](https://docs.ollama.com/windows)。

首次测试建议使用：

```powershell
ollama run qwen3.5:2b
```

V1.4.1 默认使用较快的 2B 版本；确认速度满足需求后，也可以改回表达能力更强但更慢的 `qwen3.5:4b`。第一次执行会下载模型；看到交互提示后可输入一句话确认模型能回复，然后输入 `/bye` 退出。模型会保留在本机。模型信息见 [Ollama 模型库](https://ollama.com/library/qwen3.5)。

如果 Ollama 没有在后台运行，可执行：

```powershell
ollama serve
```

不要同时启动两个占用同一端口的 Ollama 实例。

## 配置

复制 `.env.example` 为 `.env`，只在本机填写真实 Key。不要上传、截图或提交 `.env`。

### 使用 DeepSeek 文字模型（默认）

```env
TEXT_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的_DeepSeek_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
MYAI_LLM_TIMEOUT=30

MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
MYAI_VISION_TIMEOUT=120
```

### 使用 Ollama 文字模型

```env
TEXT_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:2b
OLLAMA_TIMEOUT=60
OLLAMA_KEEP_ALIVE=10m
OLLAMA_NUM_CTX=4096
OLLAMA_THINK=false

# 图片仍使用 DeepSeek Vision，所以需要保留以下配置与 Key。
DEEPSEEK_API_KEY=你的_DeepSeek_Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
MYAI_VISION_TIMEOUT=120
```

本机 Ollama API 不需要 API Key。`OLLAMA_BASE_URL` 只填服务根地址，不要追加 `/api/chat`。首次模型加载仍可能较慢；`OLLAMA_TIMEOUT` 只控制最长等待时间，并不会提高速度。配置更改后完全退出并重启 MyAI。

性能配置含义：

- `OLLAMA_KEEP_ALIVE=10m`：回复后让模型在内存/显存中保留 10 分钟。
- `OLLAMA_NUM_CTX=4096`：限制本地推理上下文；更大并不一定更快。
- `OLLAMA_THINK=false`：关闭额外思考输出，适合普通聊天。需要复杂推理时可以手动改成 `true`。

`TEXT_PROVIDER` 优先于旧配置名 `MYAI_LLM_PROVIDER`。为了避免含糊，升级后建议只保留 `TEXT_PROVIDER`。V1.4 不提供 GUI 切换按钮，GUI 切换计划留给 V1.5。

## 运行

```powershell
python gui.py
```

文字对话会走 `TEXT_PROVIDER` 指定的服务。选择图片、发送纯图片或文字加图片的 GUI 操作与 V1.3.2 相同。当前或最近历史中包含图片时，整段上下文继续交给 DeepSeek Vision，以便对图片进行追问。

## 数据与升级安全

默认数据库和托管图片位置保持 V1.3.2 规则不变。升级原项目时先备份，然后覆盖源码，但保留原 `.env`、`memory.db` 和 `%LOCALAPPDATA%\MyAI\images`（或自定义 `MYAI_DATA_DIR`）内容。

交付包不会包含 `.env`、聊天数据库、历史图片、缓存或虚拟环境。程序只从项目目录加载 `.env`；测试在导入项目模块前设置 `MYAI_LOAD_DOTENV=0`，不会读取真实配置，也不会发起真实 DeepSeek/Ollama 请求。

## 项目结构

```text
gui.py                  原有界面与后台请求线程
ai.py                   聊天流程；按是否含图片选择文字/Vision Provider
context.py              人格、情绪、关系、记忆和历史上下文
llm/
  base.py               Provider 统一接口
  config.py             DeepSeek/Ollama/Vision 环境配置
  deepseek.py           DeepSeek 纯文字 Provider
  ollama.py             V1.4 Ollama 纯文字 Provider
  deepseek_vision.py    原 DeepSeek Vision Provider（保持稳定路线）
  openai_vision.py      多模态传输与可选 OpenAI Vision
tests/
  smoke_test.py
  vision_regression_test.py
  ollama_provider_test.py
  latency_regression_test.py
```

## 离线检查

```powershell
python -m compileall -q .
python tests\smoke_test.py
python tests\vision_regression_test.py
python tests\ollama_provider_test.py
python tests\latency_regression_test.py
```

Ollama 测试会模拟 HTTP，覆盖请求 URL/JSON、超时、JSON 输出模式、完整 context 传递、Provider 选择、Vision 隔离、连接失败、模型 404、异常响应和图片拒绝。延迟回归测试确认正式回复前只有一次模型调用，三个辅助功能合并为一次 15 秒上限的后台调用。全部测试均不依赖真实 Ollama 服务。

## V1.4.1 本地验收

1. 运行全部离线检查，确认没有报错。
2. 保持 `TEXT_PROVIDER=deepseek` 启动 GUI，新建会话发送纯文字，确认原 DeepSeek 文字路线正常。
3. 发送纯图片和文字加图片，确认 DeepSeek Vision 能理解图片，且没有复现 HTTP 400。
4. 执行 `ollama run qwen3.5:2b` 完成下载和单独试聊；退出交互后确保 Ollama 后台服务仍在运行。
5. 改为 `TEXT_PROVIDER=ollama` 并重启 MyAI。在新会话进行纯文字聊天，确认小悠的人格语气正常。
6. 告诉小悠一项稳定偏好，继续聊几轮并重启程序，确认记忆、情绪、关系和会话历史仍生效。
7. 在 Ollama 文字模式下上传图片，确认图片仍走 DeepSeek Vision；随后纯文字追问历史图片，确认仍能识图。
8. 分别停止 Ollama、将 `OLLAMA_MODEL` 临时改为不存在的名称，确认 GUI 不冻结并显示可操作的中文错误；验证后恢复配置。
9. 断网但保持 Ollama 运行，进行不含任何当前/历史图片的纯文字聊天，确认本地路线可用。标题、状态和记忆分析同样使用所选文字 Provider。

真实 API 权限、网络、模型速度和 GUI 点击流程需要在用户机器上完成上述人工验收。验证稳定前不要发布或提交 GitHub。

## V1.3.2 兼容说明

DeepSeek Vision 仍固定使用已验证的 `deepseek-v4-flash-vision-exp` 和官方最小 Chat Completions 请求。环境中的错误 Vision 模型名会安全回退，直接构造错误配置会在联网前拒绝。图片仅出现在 user 消息中，base64 只在发送请求时生成，不写入数据库；HTTP 错误日志继续使用安全分类，不记录远端任意正文、请求头、消息、图片数据或 API Key。
