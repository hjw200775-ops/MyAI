# MyAI V1.3.2

## V1.3.2 更新 · 2026-09-14

- 默认文本模型切换为 `deepseek-flash`（DeepSeek V4.1 Flash 的 API 模型名）。
- 默认视觉模型也统一为 `deepseek-flash`；保留独立的文本 / Vision Provider 架构及显式可选的 OpenAI Vision。
- 继续沿用 V1.3 的图片上传、Vision Provider、DeepSeek Vision HTTP 400 请求修复和脱敏错误处理；不新增这些已有功能。
- 配置仍通过 `.env` / `.env.example`，模板密钥留空，不硬编码密钥。已有 `.env` 不会自动更新，请在本机将 `DEEPSEEK_MODEL` 和 `DEEPSEEK_VISION_MODEL` 都改为 `deepseek-flash`。
- 同步默认值、视觉模型校验和离线回归测试；compileall、smoke test 和 12 项离线 Vision 回归测试通过。未发送真实 API 请求，未进行 GUI 人工验收。

模型名称依据：[DeepSeek 2026-09-10 官方公告](https://deepseek.com/news/deepseek-v4-1-flash/)。

## V1.3 更新 · 2026-08-31（历史记录）

- **视觉模型切换**：默认使用 DeepSeek `deepseek-v4-flash-vision-exp`，与文字模型共用 DeepSeek API Key 和服务地址。
- **保持原有功能**：文字模型、GUI 分层、三类消息和历史图片路径持久化保留；base64 仅用于请求，不存数据库。
- **配置与测试完善**：新增配置模板和安全排除规则，补充离线回归测试；编译和 smoke test 已通过，真实 API 尚待本机验证。
- **升级提醒**：旧 `.env` 中的 `MYAI_VISION_PROVIDER` 需手动改为 `deepseek`，并新增 `DEEPSEEK_VISION_MODEL`；保留原数据库和图片目录。

完整修改文件清单与验证范围见 [CHANGELOG.md](CHANGELOG.md)。

V1.3 在 V1.2 基础上增加图片选择、发送前预览与取消、纯图片/纯文字/文字加图片消息，以及可替换的 Vision Provider。多会话、会话管理、静态头像、长期记忆、情绪、关系和 Context 架构均保留。

## 配置

把 `.env.example` 复制为 `.env`，只在本机填写真实 Key。不要把 `.env` 上传、截图或提交。

```env
DEEPSEEK_API_KEY=你的_DeepSeek_Key
MYAI_LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-flash

DEEPSEEK_BASE_URL=https://api.deepseek.com
MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-flash
```

DeepSeek V4.1 Flash 继续处理无图片上下文的文字对话、标题、记忆和状态分析。含当前或历史图片的上下文默认交给独立的 DeepSeek Vision Provider，使用同一个 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`。两者保留独立配置入口，默认模型名均为 `deepseek-flash`。

视觉请求使用 OpenAI-compatible Chat Completions，user 消息包含 `text` 与 `image_url` 内容块。本地图片只在 Provider 发送请求时转成 base64 data URL，不改变原始上下文，也不将编码写入数据库。接口依据：[DeepSeek 官方图像理解文档](https://api-docs.deepseek.com/zh-cn/guides/vision/)。实际调用仍取决于账号权限和服务可用性。

**从旧配置迁移：** 若已有 `MYAI_VISION_PROVIDER=openai` 或 `none`，需在本机手动改为 `deepseek`；新增 `DEEPSEEK_VISION_MODEL`，将 `DEEPSEEK_MODEL` 和 `DEEPSEEK_VISION_MODEL` 都设为 `deepseek-flash`。无需新增第二个 Key。程序不会覆盖现有配置。

保留 OpenAI Vision 作为显式可选项：设置 `MYAI_VISION_PROVIDER=openai`，并配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`（默认 `https://api.openai.com/v1`）和 `OPENAI_VISION_MODEL`（默认 `gpt-5.4-mini`）。不会在 DeepSeek 失败后自动把图片传给其他厂商。设置 `none` 或 `disabled` 可禁用视觉服务。

配置从项目目录的 `.env` 加载，已有进程环境变量优先。`MYAI_LOAD_DOTENV=0` 可禁用配置文件读取，离线测试在导入项目模块前即启用此开关。

## 运行

```powershell
python -m pip install -r requirements.txt
python gui.py
```

点击输入框左侧的附件按钮选择 PNG、JPG/JPEG、WEBP、GIF 或 BMP（最大 20 MB）。发送前会显示不超过 180×120 的预览，可点击“取消”。GIF 第一帧和 BMP 会转换为 PNG 后发送。

## 数据与打包

发送的图片会复制到 `%LOCALAPPDATA%\MyAI\images`，数据库只保存生成后的文件名，不依赖用户最初选择的绝对路径。可用 `MYAI_DATA_DIR` 指定其他持久目录；打包时还可用 `MYAI_DB_PATH` 把数据库移到持久目录。默认数据库位置保持 V1.2 不变，因此现有聊天不会丢失。

首次运行会无损给现有 `messages` 表增加 `image_path` 和 `message_type` 字段。旧文字聊天仍按原格式加载。第一阶段只做必要的图片历史元数据和文字占位显示，不加入自动看屏幕、OCR、Live2D 或主动观察。

## 结构

```text
gui.py                 选择、预览、取消和三类消息入口
ai.py                  聊天流程；根据是否含图片选择统一 Provider
context.py             人格/情绪/关系/记忆/历史/图片组成同一上下文
media.py               图片校验、持久化和 EXE 友好路径
llm/
  base.py              统一接口与视觉能力声明
  deepseek.py          纯文字 Provider（遇到图片会明确拒绝）
  deepseek_vision.py   默认 DeepSeek Vision Provider
  openai_vision.py     共用多模态传输及可选 OpenAI Provider
  config.py            环境变量配置
memory.py              兼容迁移与最小图片历史支持
```

## 基础检查

```powershell
python -m compileall -q .
python tests\smoke_test.py
python tests\vision_regression_test.py
```

测试使用假的离线 Provider，不发起网络请求，也不读取或打印真实 `.env` Key。


## 本地验收

1. 安装依赖后执行上方 compileall 和 smoke_test。smoke test 用临时数据库、生成的测试图片和模拟客户端，覆盖默认/后备/禁用配置、三类消息、真实 Provider 请求组装、历史图片恢复、图片缺失降级及数据库不存 base64；不发网络请求。
2. 仅在本机填写 `.env`，启动 `python gui.py`。新会话发送纯文字，确认正常回复；分别发送纯图片和文字加图片，确认模型能回答图中内容。
3. 关闭并重新打开程序，选回原会话，发送“再看一下之前的图片”。原图文件即使被移动，托管目录的图片仍应可用。当前 GUI 历史显示图片文件名占位，并非历史缩略图。
4. 本次离线检查不等同于真实 API 或 GUI 人工验收；账号权限、网络和实际识图质量需要步骤 2–3 验证。

交付包不包含 `.env`、聊天数据库或历史图片。更新原项目时请保留原数据库及图片目录，备份后覆盖源码；不要把交付包当作包含旧聊天数据的完整备份。

## 2026-09-09 HTTP 400 根因与修复（历史记录）

以下旧模型名记录当时的修复；V1.3.2 当前默认与校验模型已更新为 `deepseek-flash`，请求格式与脱敏策略继续保留。

本次基于用户实际运行并回传的项目检查配置（只比较配置项，不输出值）。确认
`DEEPSEEK_API_KEY`、DeepSeek Provider 和官方 API 根地址均有效，但运行时
`DEEPSEEK_VISION_MODEL` 不是官方模型名，而是被误填成了与 `DEEPSEEK_API_KEY` 相同的值；旧日志把 model 显示为
`[redacted]` 正是模型字段误填密钥的证据。错误的 model 被原样发往 API，触发 HTTP 400。

修复后，DeepSeek Vision 配置仅接受当前官方模型
`deepseek-v4-flash-vision-exp`；环境变量误填或拼写错误时安全回退到该模型，直接构造
错误配置的扩展代码则在联网前给出本地错误。DeepSeek 请求使用官方最小格式，不附加
thinking、detail、temperature、tools 或 response_format；最终 HTTP JSON 只有 `model` 和
`messages`。历史图片仍被保留，但图片块只能来自 user 消息。

400 日志现在附加安全的 `remote=` 分类，例如 `model_does_not_support_image`、
`image_must_be_in_user_message`、`invalid_image_base64` 或 `request_too_large`。远端任意正文、
请求头、API Key、消息正文和 base64 都不会写入日志；无法安全识别的远端 message 显示为
`unrecognized_remote_message_hidden`。

## 2026-08-31 Vision 故障修复说明（历史记录）

### 结论与证据边界

原压缩包没有 `.env`、运行日志或真实 API 错误，因此无法确认用户当时的实际 Provider、账户权限、网络状态或 HTTP 状态码。不能把某一个远端原因当作已经复现的根因。

已经确认的代码缺陷：

- `ai.py` 强制传入视觉超时 45 秒，覆盖 `MYAI_VISION_TIMEOUT`，调整配置无法延长等待。
- DeepSeek Vision 最终改为官方最小请求，不再额外传 thinking 控制参数。
- API 异常被统一捕获并丢弃，HTTP 状态及错误类别全部消失，这是只能看到通用提示的确定根因。
- 图片 MIME 原先按扩展名猜测，且没有检查 API 图片尺寸及累计请求体限制。这些属于防御性修复，并非已经证明的此次触发原因。

原来的默认 Provider、模型名、API 根地址、`user.content` 中的 `text` / `image_url` 结构是正确的，不需要换成另一个厂商或另一个 API。

### 官方核对（2026-08-31）

使用 OpenAI SDK 的 `client.chat.completions.create`：

- API 根地址：`https://api.deepseek.com`
- HTTP endpoint：`POST https://api.deepseek.com/chat/completions`
- 模型：`deepseek-v4-flash-vision-exp`
- Key：本项目读取 `DEEPSEEK_API_KEY`，由 SDK 放入认证头。
- 图片块：`{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}`
- 图片只放在 user 消息中。无需切换到 Responses 或 Anthropic 接口。
- DeepSeek Vision 不附加额外参数；SDK 超时只控制客户端，不进入 HTTP JSON。

来源：[Vision](https://api-docs.deepseek.com/guides/vision/)、[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[API 入门](https://api-docs.deepseek.com/)。

### 当前配置与诊断（V1.3.2）

已有 `.env` 不会自动被模板覆盖。确认 `MYAI_VISION_PROVIDER=deepseek`，`DEEPSEEK_VISION_MODEL=deepseek-flash`，`DEEPSEEK_BASE_URL=https://api.deepseek.com`，`MYAI_VISION_TIMEOUT=120`。保留本机 `DEEPSEEK_API_KEY`。文字配置保留 `MYAI_LLM_PROVIDER=deepseek`、`DEEPSEEK_MODEL=deepseek-flash`、`MYAI_LLM_TIMEOUT=30`。不需要 OPENAI_API_KEY。

进程环境变量优先于 `.env`；旧的 `MYAI_VISION_PROVIDER=openai` 仍会明确选择 OpenAI。修改后完全退出再启动。不要把完整 `/chat/completions` 路径写入 base_url。120 秒为 SDK 操作超时，不是整个聊天流程的总时限；状态分析和标题生成还有独立请求。Vision 禁止 SDK 自动重试，避免叠加等待。

从终端执行 `python gui.py` 可查看安全日志。日志显示实际 provider、model、endpoint、key 是否存在、超时、HTTP 状态、异常类型及经过允许列表识别的 `remote=` 错误类别。远端原始错误体可能回显任意凭据，因此原始正文不记录；也不记录请求头、消息正文、base64 或 traceback。未知错误内容一律隐藏。默认输出到终端，不新建日志文件。请勿开启 SDK 的调试级别请求日志。

常见结果：401 检查 Key；402 检查余额；403 检查权限；404 检查模型和地址；400 检查模型能力及图片格式/尺寸；429 稍后重试；5xx 服务端故障；APITimeoutError 检查网络并适当增大超时；APIConnectionError 检查代理、网络或证书。HTTP N/A 表示没有可用的 HTTP 状态，并非 200。

### 修改文件

`llm/config.py`：有效超时默认 120 秒、拒绝非有限超时、纠正无效/凭据形态的模型配置、配置 repr 不暴露 Key。
`llm/deepseek_vision.py`：校验官方模型并构造最小 DeepSeek Vision 请求。
`llm/openai_vision.py`：真实格式 MIME、无损 base64、必要时转 PNG、尺寸/体积/数量检查、地址检查、安全错误封装、禁用自动重试。
`llm/diagnostics.py`：新增安全诊断。
`ai.py`：主聊天尊重 Provider 超时，返回安全错误信息。
`context.py`：历史图片仅从 user 消息构建，异常 assistant 图片元数据不会发到 API。
`gui.py`：最外层异常也经过安全诊断。
`.env.example`、`README.md`、`requirements.txt`、`tests/smoke_test.py`、`tests/vision_regression_test.py`：配置、文档及回归检查。

已检查但无需改变：`llm/base.py`、`llm/deepseek.py`、`llm/__init__.py`、`media.py`、`memory.py`。Provider 解耦和持久化结构保持不变。

### 离线验证与升级验收

```powershell
python -m pip install -r requirements.txt
python -m compileall -q .
python tests/smoke_test.py
python tests/vision_regression_test.py
```

构造层使用假 Key 和 HTTP MockTransport，不发真实模型请求。覆盖准确 endpoint、最小 HTTP JSON、超时传递、真实 MIME/base64、图片仅处于 user 消息、状态码错误、安全远端分类、网络异常、脱敏、OpenAI 隔离、消息不被原地修改、三类消息和图片历史；失败时只保存用户消息，不伪造 assistant 回复。SDK 兼容验证使用项目锁定的 openai 3.6.0。GUI 未人工点击验收；没有消耗真实 Key 额度进行联网请求。

升级前备份原项目。覆盖源码时保留原 `.env`、`memory.db` 和图片目录；不要删除 `%LOCALAPPDATA%/MyAI/images` 或自定义 `MYAI_DATA_DIR`。新包不携带个人数据。先新建会话测试纯文字，再发送小 PNG/JPG 和“这是啥”。若失败，记录屏幕及终端的安全错误摘要，不要提供 Key 或 `.env`。成功后重启程序，在原会话追问图片，验证历史仍可用。GUI 历史保持原有文件名占位显示，不新增历史缩略图。
