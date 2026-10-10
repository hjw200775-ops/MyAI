# MyAI V1.6.1 — 研究驱动基础设施

V1.5 在 V1.4.2 稳定代码上增加“AI 设置”：无需修改 `.env` 或重启，即可让后续纯文字消息在 DeepSeek 云端与 Ollama 本地之间切换。DeepSeek Vision、图片上传、HTTP 400 修复、人格、长期记忆、情绪、关系、会话历史和标题容错保持原路线。


用户已于 2026-10-11 确认 V1.6.1 本地测试通过。本次 GitHub 发布包含 V1.6 与 V1.6.1 增量更新，分别见 CHANGELOG.md。升级前备份并保留自己的本地配置和数据库。

## V1.6.1 新增（基于完整 V1.6）

在 V1.6 Temporal Awareness 上增加 replannable proactive timeline foundation、category-aware memory retention foundation 和 short-term affect foundation。控制在基础设施范围；真正主动发送仍属于 V1.7。本版没有主动消息后台任务、弹窗、不可撤销闹钟或新增网络请求。

- `proactive_timeline.py`：`PendingActionRepository` / `ProactiveTimelineService` 提供 create/schedule、get、list_due_actions/get_due_actions、defer、cancel、expire、mark_completed、review/reconsider。到达 earliest_at 只成为 eligible，状态仍为 pending/deferred；review 的 eligible 也不授权发送。mark_completed 仅是调用方显式记账，不执行消息。ReviewContext 为最新上下文、idle duration、最近主动行为、输入/全屏状态预留字段，本版不采集屏幕或输入活动。
- `foundation_time.py`：复用 V1.6 TimeContextService 的可注入 clock，维护进程内时间高水位。系统时钟倒退时冻结基础设施有效时间，直到时钟追上，避免重新激活/延长已衰减状态。跨重启不持久化高水位；终态保存在 SQLite，过期情绪不会跨重启恢复。损坏 clock 拒绝操作，损坏队列时间戳 fail closed 为 expired。earliest/expires 使用带时区 ISO 时间；兼容旧本地无时区时间戳。earliest 必须早于 expires，expires 必须晚于当前时间；defer 必须真正向后移动且早于 expires。
- `memory_retention.py`：旧 memories 表原 category 继续表示主题；另加 retention_category、confidence、expires_at、retention_status、metadata。旧记录保留为 active explicit_fact，历史内容不重新推断；preference 新写入明确标注。五元组 load_memories API 保持兼容，只返回有效 active 记忆，candidate/expired/敏感记录不进入 prompt。TTL 到期或时间戳损坏时标记 expired，不删除历史行。
- `MemoryRetentionService.save`：explicit_fact/preference 正常保存；temporary_state_or_plan 要求 TTL 或 expires_at；inferred_trait_or_value 一律 candidate（高 confidence 也不自动提升）；sensitive_inference 一律 abstain，连 metadata 也不落盘。confidence 可为空，有限范围 0–1，不使用论文实验百分比作为产品阈值。
- 原自动记忆整理请求继续复用，没有额外模型调用。增加“仅明示事实/偏好”的 prompt 约束和保守关键词筛查；敏感线索 abstain、推断线索 candidate、临时线索默认 24 小时 TTL。规则并非完整语义识别，无法保证识别所有未标注推断；有明确来源的扩展应调用 typed retention API。推断性更新不覆盖已有事实，candidate 不在 GUI 显示为“已记住”。24 小时是可替换的工程默认 TTL，不是研究阈值。旧手动记忆操作按用户明确写入保留。
- `affect_state.py`：独立可选 ShortTermAffect，valence [-1,1]、arousal/confidence [0,1]、updated_at、expires_at；TTL 默认 30 分钟，最多 24 小时，连续线性衰减，到期/坏时间戳回 neutral。只保存在进程内，不接入回复、永久档案、emotion.py、Live2D 或 TTS；不新增模型、摄像头或依赖。

数据库在原 init_database 的事务内幂等迁移：新增 pending_actions 表及 status 索引，memories 仅 ADD COLUMN，不改写旧内容/主题/时间戳/ID。升级前备份旧数据库；保留自己的 .env、settings、托管图片，不要用测试库覆盖。测试必须使用隔离入口，不能指向个人数据库：

```text
python -m compileall -q .
python tests/run_offline.py tests/foundations_test.py
```

用同一入口运行全部 `tests/*_test.py`。入口阻断 socket 连接，禁用 dotenv 并隔离数据库/图片/settings。

### V1.6.1 本地验收

1. 备份后以旧数据库启动两次，确认会话、记忆、情绪、关系和标题保留，重复迁移正常。
2. DeepSeek → Ollama → DeepSeek 切换、设置持久化、断网时间问答和会话时长继续累计。
3. 图片上传、历史图片追问和 HTTP400 提示保持原表现。
4. 运行 foundations_test：到期/复核只影响队列，GUI 不应主动发消息或弹窗。
5. 验证明确偏好仍可记住；candidate 不出现在回复上下文；临时记忆到期不再使用；敏感推断不落库。保守规则可能漏判或误判，先在测试数据上观察。
6. affect 独立测试衰减/到期 neutral，本版普通回复和原 emotion.py 表现保持不变。

## V1.6 新增

基于用户已测试通过的完整 V1.5.1 稳定源码。新增完全离线的本地时间感知、互动间隔和会话时长；DeepSeek/Ollama 共用 Temporal Context，Vision 同样通过原 Context Builder 获得环境信息。无网络时间 API、无新增依赖。主动聊天留给 V1.7；本版没有定时器或后台监控。

- 系统日期、时间、星期、小时与自然时段：05–09 清晨、09–12 上午、12–14 中午、14–18 下午、18–23 晚上、其余深夜（左闭右开）。
- 时间来自 `datetime.now().astimezone()`，遵循操作系统时钟与时区；Python 计算时间差，模型无需日期算术。
- 上次有效互动是所有保留会话中按消息 ID 最新的非空用户文字或图片输入；另提供当前聊天的上一条用户消息间隔。助手回复、标题更新、后台分析不算用户互动。API 失败但已保存的用户输入仍算互动。
- 历史时间复用 SQLite `messages.created_at`，无需 schema 迁移；兼容 V1.5.1 无时区本地 ISO 时间戳。缺失/损坏时间戳显示未知，不冒用更早记录；系统时间倒退时差归零。删除聊天也会删除其中的历史时间依据。
- 本次会话指当前程序运行期间，每个聊天首次有效输入至当前输入的时间；开始时间保存在进程内存，重启后重新计时，切换聊天/Provider 不重置已有聊天计时。它不等于历史聊天创建日期，也不是实际活跃时长。
- 当前输入保存前捕获不可变快照，再传入 `ContextOptions.time_context`；避免保存后互动间隔变成零。仅在问候、作息、久别或当前话题相关时自然提及时间，普通技术问题不应机械报时。
- `TemporalContext` 提供 `current_period`、`idle_duration`（秒或 None）、`last_interaction`、`session_started_at`、`session_duration`（秒）等接口供 V1.7 使用。

升级前备份现有项目；覆盖源码并保留自己的 `.env`、数据库、settings 和托管图片。交付包没有私人数据。若采用新目录运行，可通过原有 `MYAI_DB_PATH` 指向已备份的旧数据库。

### V1.6 重点验收

1. 首次无历史时问日期、星期、当前时段；不得虚构上次见面。
2. 间隔几分钟后发送消息，确认读取的是发送前间隔；新建另一聊天也能感知全局最近互动。
3. 23:xx、00:xx、05:00 跨日和时段边界（可先使用 fake clock 测试，避免修改系统时间）。
4. 同一聊天 DeepSeek → Ollama → DeepSeek 切换，会话时长继续累计；Ollama 断网纯文字聊天仍可使用时间信息。
5. 普通编程问题不应反复报时；问候、困倦、久别话题自然使用时间。
6. 上传图片及追问历史图片，确认原 Vision 路线、HTTP400 提示、标题、记忆、关系、设置持久化仍正常。

## V1.5.1 修订

- 配置字段严格检查类型、模型名和服务根地址；拒绝已知凭据落入偏好文件，写入失败清理临时文件。
- Provider 单例及客户端初始化加锁；相同配置复用，旧客户端在最后一个请求释放 Provider 后关闭。
- 提交消息时固定文字 Provider，同轮后台分析继续使用该选择；之后提交的消息使用新选择。
- 连接检查结果通过队列由 GUI 主线程处理，关闭窗口后停止更新，配置变更后忽略过期结果。
- 关系状态的读取、计算和写入一起加锁，避免并发丢失更新。
- Ollama 状态检查识别省略 `:latest` 的模型名；非法地址给出固定安全提示。
- 打包模式数据库写入用户目录，`.env` 从可执行文件所在目录读取；源码模式数据位置保持原规则。
- 补回缺失的 `.env.example`，新增离线稳定性回归测试。详见 `AUDIT.md`。

正在执行的请求继续完成，不会在切换时关闭其客户端。图片历史仍由独立 Vision Provider 处理。
保留已有显式 OpenAI Vision 环境配置兼容能力；默认 DeepSeek Vision 不跟随文本选择。

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

源码运行的数据库和托管图片位置保持原规则。打包运行时数据库默认位于 `%LOCALAPPDATA%\MyAI\memory.db`，已有数据库需自行备份后复制到该目录；`MYAI_DB_PATH` 可覆盖此位置。升级原项目时先备份，然后覆盖源码，但保留自己的 `.env`、`memory.db` 和 `%LOCALAPPDATA%\MyAI\images`（或自定义 `MYAI_DATA_DIR`）。V1.5 的用户模型偏好位于 `%APPDATA%\MyAI\settings.json`。

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
python tests\stability_test.py
python tests\smoke_test.py
python tests\title_resilience_test.py
python tests\vision_regression_test.py
# temporal_test 必须通过隔离入口运行（临时数据库、屏蔽网络）
python tests\run_offline.py tests\temporal_test.py
```

测试全部使用模拟 Provider/HTTP，不需要真实 DeepSeek/Ollama 服务，也不会发送真实 API 请求。

## V1.5 本地验收

1. 安装依赖并运行全部离线检查。
2. 启动 GUI，确认标题为 MyAI v1.6，且“AI 设置”显示当前文字 Provider。
3. 选择 DeepSeek，发送纯文字，确认原 `deepseek-flash` 路线正常。
4. 选择 Ollama，填写本机模型与 Base URL，点击“检查连接”，保存后不重启直接发送下一条纯文字。
5. 在两个 Provider 间往返切换，确认每次保存后下一条纯文字立即使用新选择。
6. 确认人格、长期记忆、情绪、关系、会话历史和自动标题仍正常。
7. 在 Ollama 文字模式上传图片并追问历史图片，确认图片仍由 DeepSeek Vision 理解。
8. 分别停止 Ollama、填写不存在的模型，确认状态提示可区分连接问题和模型缺失，GUI 不冻结。
9. 查看 `%APPDATA%\MyAI\settings.json`，确认仅有三个非敏感字段，没有 API Key。
10. 临时破坏或删除 settings 文件，重新启动，确认程序用安全默认值正常打开。

真实 API 权限、网络、模型速度和 GUI 点击流程需在用户机器上完成。验证稳定前不要发布或提交 GitHub。
