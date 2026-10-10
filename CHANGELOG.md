# 更新日志

## 2026-10-10 · 研究驱动增量更新

基于 V1.6 Temporal Awareness，新增可重新规划主动时间队列、分类记忆保留和可衰减短期 affect 基础设施。真正主动发送留给 V1.7。

- 新增 pending_actions SQLite 表、repository/service 与最新上下文复核 hook。到期只 eligible，无发送器、后台定时器或弹窗。
- memories 兼容 ADD COLUMN 迁移；明确事实/偏好 active、临时信息 TTL、推断 candidate、敏感推断 abstain。自动整理增加保守规则，不增加模型调用。
- 独立内存 affect 状态，连续衰减、TTL/异常回 neutral，不替换 emotion.py。
- 共用 V1.6 可注入系统时钟，基础设施时间高水位处理倒退；Temporal Context 原实现保持逐字节不变。
- 新增确定性离线基础设施测试；Provider、Vision、settings、图片和 HTTP400 修复保持原实现。

## 2026-10-08 · MyAI V1.6 — Temporal Awareness

- 基于完整 V1.5.1 稳定版；新增完全离线的本机日期、时间、星期、小时、自然时段、互动间隔及会话时长。
- DeepSeek/Ollama 共用 Context Builder 的 Temporal Context；保存当前输入前计算互动间隔。Vision 原链路保留。
- 复用 SQLite messages 时间戳，无 schema 变更；异常时间戳未知、负差归零；会话开始保存在进程内存，Provider 切换不重置。
- 新增固定时钟与模拟传输回归；主动聊天留给 V1.7，不加入定时器、后台监控或语音功能。

## 2026-10-11 · GitHub 发布与验收

- 用户已确认 MyAI V1.6.1 本地测试通过；同步 V1.6 离线时间感知与 V1.6.1 研究驱动增量源码。
- 分别保留 V1.6 和 V1.6.1 更新条目；本次发布前复验编译检查和全部隔离离线测试。
- 发布仅包含源码、测试、文档、空密钥配置模板与原角色头像；排除本地 .env、数据库、会话记录、虚拟环境、缓存、日志和私人图片。
- 真正主动发送仍属于 V1.7；到期与复核 eligible 均不会执行消息。

## 2026-10-08 · MyAI V1.5.1 — 并发、配置与打包稳定性修复

- 每次聊天请求固定使用发送时选定的文字 Provider，避免切换设置影响正在进行的回复或后台分析。
- Provider 热切换和懒加载增加线程同步，相同配置不再重复创建客户端。
- DeepSeek 与 OpenAI Vision 客户端创建增加线程保护，并在对象回收时安全关闭连接。
- Ollama 地址校验拒绝凭据、路径、查询参数与非法端口，并兼容未显式填写的 `:latest` 模型标签。
- AI 设置连接检查改为线程安全队列回传，保存失败不再向界面暴露底层异常细节。
- 设置文件增加模型名、URL 和敏感凭据校验，临时文件写入失败时可以安全清理。
- 打包运行时从可执行文件目录读取 `.env`，数据库默认写入用户本地数据目录并自动创建父目录。
- 关系状态更新放入同一锁范围，避免并发更新覆盖。

## 2026-09-27 · MyAI V1.5 — GUI 模型切换与用户设置

- 主界面新增“AI 设置”，显示并切换 DeepSeek 云端 / Ollama 本地文字 Provider。
- 保存后热替换文字 Provider，后续纯文字消息无需重启即可生效。
- 新增 `settings.py`，将 `text_provider`、`ollama_model`、`ollama_base_url` 持久化到 `%APPDATA%\MyAI\settings.json`。
- 缺失、损坏、字段不完整或非法的 JSON 安全回退到 `.env` / 内置默认值；写入使用临时文件与原子替换。
- Ollama Provider 新增 `/api/tags` 状态检查，可区分不可连接、超时、异常响应和模型未安装。
- Vision Provider 保持独立 DeepSeek 路线，切换文字 Provider不修改或重建 Vision Provider。
- `.env` 继续保存 API Key、高级运行参数与首次运行默认值；用户设置永不保存 API Key。
- 新增完全离线的设置、保存重载、损坏回退、双向热切换、Ollama 字段更新、Vision 隔离和密钥排除测试。
- 保留 V1.4.2 的标题容错、DeepSeek/Ollama 空响应保护，以及现有人格、记忆、情绪、关系、会话与图片功能。

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

