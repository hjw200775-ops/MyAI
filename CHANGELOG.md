# 更新日志

## 2026-09-26 · MyAI V1.4.2 — 空返回容错修复

- 修复 `_clean_title()` 对空标题执行 `.strip().splitlines()[0]` 引发的后台线程 `IndexError`。
- 标题为空、缺失或只有空白时，回退到清理后的用户首条文本；仍不可用时保留“新对话”。
- 标题、记忆、情绪和关系辅助结果缺字段或格式异常时安全跳过，GUI 后台线程增加最终异常保护。
- DeepSeek/Ollama 文字返回为空或响应结构异常时给出明确中文错误。
- 新增标题与辅助任务回归测试，并扩充 DeepSeek/Ollama 离线返回格式测试。

## 2026-09-17 · MyAI V1.4.1 — 本地回复延迟优化

- 移除正式回复前的情绪/关系分析等待，并移除正式回复后的同步记忆与标题等待。
- 将情绪、关系、记忆和标题合并成一个后台 JSON 分析请求，超时 15 秒。
- GUI 先显示并解锁输入，再异步显示记忆提示、刷新生成的会话标题。
- Ollama 新增 `OLLAMA_KEEP_ALIVE`、`OLLAMA_NUM_CTX`、`OLLAMA_THINK`，默认分别为 `10m`、`4096`、`false`。
- 请求加入官方支持的 `keep_alive`、`options.num_ctx` 和 `think` 参数。
- 新增延迟流程回归测试，确保可见回复只触发一次前台模型调用。
- 保留 DeepSeek 文字、DeepSeek Vision、HTTP 400 修复、图片、上下文、数据库和头像路线。

## 2026-09-15 · MyAI V1.4 — Ollama 本地文字 Provider

### 新增
- 新增 `llm/ollama.py`，通过 Ollama 原生 `/api/chat` 提供本地纯文字生成。
- 新增 `TEXT_PROVIDER=deepseek|ollama`、`OLLAMA_BASE_URL`、`OLLAMA_MODEL` 和 `OLLAMA_TIMEOUT`。
- 新增 `tests/ollama_provider_test.py`，离线验证请求构造、context、选择逻辑、Vision 隔离与错误处理。

### 兼容与安全
- 保留旧 `MYAI_LLM_PROVIDER` 作为低优先级兼容配置；默认仍为 DeepSeek。
- Ollama 复用现有 ContextBuilder，不复制或改写人格、记忆、情绪、关系与历史逻辑。
- 含当前或历史图片的请求仍只走原 DeepSeek Vision 路线；没有自动跨 Provider 回退。
- GUI 继续用原后台线程，不增加切换按钮或大规模重构。
- 本地连接、超时、模型 404、无效响应与空回复使用固定中文错误，不回显远端任意正文。
- 交付包排除 `.env`、密钥、数据库、历史图片、缓存和虚拟环境。

### 修改文件
- 新增：`llm/ollama.py`、`tests/ollama_provider_test.py`。
- 修改：`llm/config.py`、`llm/__init__.py`、`gui.py`、`tests/smoke_test.py`、`.env.example`、`README.md`、`CHANGELOG.md`。
- 保持：`ai.py`、`context.py`、DeepSeek 文字/Vision Provider、图片与数据库逻辑、其余 GUI 行为及依赖列表。

## 2026-09-09 · DeepSeek Vision HTTP 400 修复

- 确认实际 `.env` 把 `DEEPSEEK_VISION_MODEL` 误填成与 `DEEPSEEK_API_KEY` 相同的值；不输出或记录密钥。
- DeepSeek Vision 环境配置误填时自动使用 `deepseek-v4-flash-vision-exp`，扩展代码直接传错模型时在联网前拒绝。
- DeepSeek Vision 改用官方最小 Chat Completions 请求，移除非必要的 thinking 与 image detail 字段。
- 保留按真实文件内容检测 MIME、base64 data URL、图片仅处于 user 消息、历史图片和数据库持久化。
- 400 诊断加入安全 `remote=` 分类；原始错误正文、API Key、对话文本和 base64 永不写日志。
- 扩展离线 Vision 测试，断言 endpoint、模型、HTTP JSON 精确字段、角色、MIME/base64、SDK 超时和脱敏。

## 2026-08-31 · MyAI V1.3 — DeepSeek Vision 更新

### 新增
- 新增 `llm/deepseek_vision.py`，提供独立的 DeepSeek Vision Provider。
- 新增 `DEEPSEEK_VISION_MODEL`，默认值为 `deepseek-v4-flash-vision-exp`。
- 新增 `.env.example` 配置模板和 `.gitignore`，避免误提交密钥、数据库和缓存。

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
| `.env.example` | 新增安全配置模板 |
| `.gitignore` | 新增本地配置、数据库及缓存排除规则 |
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
- 交付包不含真实 `.env`、API Key、聊天数据库、历史图片和虚拟环境；未更新 GitHub 仓库。
