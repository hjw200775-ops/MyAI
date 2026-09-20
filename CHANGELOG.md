# 更新日志

## 2026-09-21 · MyAI V1.4.1

- 基于最新 V1.3.2 `deepseek-flash` 基线新增独立 Ollama 纯文字 Provider；图片仍由原 DeepSeek Vision 处理。
- 新增 `TEXT_PROVIDER`、`OLLAMA_BASE_URL`、`OLLAMA_MODEL`、`OLLAMA_TIMEOUT`、`OLLAMA_KEEP_ALIVE`、`OLLAMA_NUM_CTX`、`OLLAMA_THINK`；保留旧配置名兼容。
- 正文回复先显示；情绪、关系、记忆和标题合并为一次后台分析，避免辅助请求串行阻塞 GUI。
- 新增 Ollama 离线请求与延迟流程测试；保留现有 smoke 和 Vision 回归测试。
- 未将 `.env`、API Key、数据库、历史图片或生成缓存加入仓库。

## 2026-09-14 · MyAI V1.3.2

- 默认文本模型切换为 `deepseek-flash`（DeepSeek V4.1 Flash 的 API 模型名）。
- 默认视觉模型也统一为 `deepseek-flash`；保留独立的文本 / Vision Provider 架构及显式可选的 OpenAI Vision。
- 继续沿用 V1.3 的图片上传、Vision Provider、DeepSeek Vision HTTP 400 请求修复和脱敏错误处理；不新增这些已有功能。
- 配置仍通过 `.env` / `.env.example`，模板密钥留空，不硬编码密钥。已有 `.env` 不会自动更新，请在本机将 `DEEPSEEK_MODEL` 和 `DEEPSEEK_VISION_MODEL` 都改为 `deepseek-flash`。
- 同步默认值、视觉模型校验和离线回归测试；compileall、smoke test 和 12 项离线 Vision 回归测试通过。未发送真实 API 请求，未进行 GUI 人工验收。

以下条目为历史记录，旧模型名仅描述当时版本。

## 2026-09-09 · DeepSeek Vision HTTP 400 修复

- 修复 `DEEPSEEK_VISION_MODEL` 误填时导致的 HTTP 400，并固定使用 `deepseek-v4-flash-vision-exp`。
- DeepSeek Vision 使用最小 Chat Completions 请求，不发送非必要的 thinking 与 image detail 字段。
- 图片内容块仅允许出现在 user 消息，按实际图片内容检测 MIME 并生成 base64 data URL。
- 新增脱敏错误分类，不记录远端原始正文、API Key、消息正文或 base64 图片数据。
- 扩展 smoke/offline 测试，覆盖 endpoint、模型、请求 JSON、角色、MIME/base64、超时和脱敏。

## 2026-08-31 · MyAI V1.3 — DeepSeek Vision 更新

### 新增
- 新增 `llm/deepseek_vision.py`，提供独立的 DeepSeek Vision Provider。
- 新增 `DEEPSEEK_VISION_MODEL`，默认值为 `deepseek-v4-flash-vision-exp`。
- 更新 GitHub 已有的 `.env.example` 配置模板和 `.gitignore`，保留原有隐私排除规则并补充数据库临时文件规则。

### 调整
- 默认视觉 Provider 改为 `deepseek`，与文字 Provider 共用 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）。
- 图像请求使用 OpenAI-compatible Chat Completions 的 `text + image_url` 内容块；本地图片仅在请求组装时编码为 base64 data URL。
- 保留 OpenAI Vision 为手动可选后备，不会在 DeepSeek 失败后自动将图片发送给其他厂商。
- 视觉请求处理保留直接传入的 `image_url`，限制图片内容块只能位于 user 消息，并明确拒绝未知内容块。
- 配置文件加载限定为项目目录的 `.env`；增加 `MYAI_LOAD_DOTENV=0`，供离线测试禁用配置文件读取。

### 保持不变
- 文字模型仍为 DeepSeek `deepseek-v4-flash`。
- 视觉调用仍位于 Provider 层，没有写入 GUI。
- 纯文字、纯图片、文字加图片入口及历史图片路径持久化保留。
- 数据库仅保存图片文件名，不保存 base64；GUI 历史仍显示图片文件名占位。
- 无需新增运行依赖；人格、记忆、情绪和关系逻辑保持不变。

### 修改文件
| 文件 | 更新内容 |
| --- | --- |
| `llm/config.py` | 默认视觉配置、共享 DeepSeek Key/base URL、可禁用的配置文件加载 |
| `llm/deepseek_vision.py` | 新增 DeepSeek 视觉 Provider |
| `llm/openai_vision.py` | 共用多模态请求处理和对应供应商的缺 Key 提示 |
| `llm/__init__.py` | 注册 DeepSeek 视觉 Provider，保留 OpenAI 和禁用模式 |
| `.env.example` | 更新 DeepSeek Vision 配置，保留私有数据目录示例 |
| `.gitignore` | 保留仓库原有规则，补充数据库临时文件排除 |
| `tests/smoke_test.py` | 新增配置、请求格式和历史图片持久化回归检查 |
| `README.md` | 更新配置、迁移及本地验证说明，添加更新摘要 |
| `CHANGELOG.md` | 本更新日志 |

已检查但无需修改：`llm/base.py`、`llm/deepseek.py`、`ai.py`、`context.py`、`media.py`、`gui.py`、`memory.py`、`requirements.txt`。

### 升级操作
备份原项目并保留原 `.env`、数据库和托管图片目录，然后更新源码。在本机 `.env` 中调整：

```env
MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

继续使用原 `DEEPSEEK_API_KEY`，无需第二个 Key。旧配置中显式设置的 `openai` 或 `none` 不会被默认值覆盖，必须手动调整。

### 验证结果与范围
- `compileall`：通过。
- `smoke_test`：PASS；使用模拟客户端、测试图片和临时数据库，不读取真实 `.env`，不发起模型网络请求。
- 覆盖三类消息、历史图片恢复、原图删除后托管副本可用、历史图片追问、缺失图片降级，以及数据库不存 base64。
- 未进行真实 API 调用和 GUI 人工验收；模型权限、网络及实际识图质量需在本机验证。
- 交付包不含真实 `.env`、API Key、聊天数据库、历史图片和虚拟环境。
