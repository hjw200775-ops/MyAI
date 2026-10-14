# MyAI V1.6.2 Stable 合并与验证报告

## 合并文件
新增 companion_loop.py（含 DecisionEngine、ActionReviewer）、user_activity.py、companion_events.py、core/companion_runtime.py。
增量更新 memory.py（事件表迁移）、proactive_timeline.py（审核字段及状态）、time_context.py（后台采样不建立聊天会话）。这三份后端文件经差异检查，仅包含上述增量；其余原有后端保留。
沿用 V1.6.1 affect_state.py 的 short-term affect 接口。新增 tests/companion_test.py，更新 README.md、CHANGELOG.md，提供空密钥 .env.example。

## UI 保护
原始基线为引用聊天实际上传的 MyAI_V1.6.1.zip，不是旧开发包。
gui.py、ui/ 的布局、样式、头像、标题栏、侧栏、聊天窗口、设置页面和全部 assets/ 文件保留。
仅 ui/app.py 增加生命周期适配调用，ui/main_window.py 更新窗口版本标题。完整 SHA-256 对照见 UI_FILE_MANIFEST.json。
Companion Runtime 每五分钟在后台运行，主线程先读取会话、Provider、请求状态和输入框草稿；草稿或请求处理中标记 busy；防止循环任务重叠。不自动发送消息。
现有 core/events.py 和 companion_events.py 保留各自用途：前者是界面生命周期事件，后者是数据库中的共同经历事件。

## 数据库变化
pending_actions 增加 reviewed_ready INTEGER NOT NULL DEFAULT 0 与 review_outcome TEXT。
新增 companion_events 表及时间索引。保留原有表和数据；迁移可重复运行。
使用合成 V1.6.1 pending_actions 旧结构测试，迁移两次及 init_database 两次后旧行仍保留。
没有打开或修改上传包中的私人 memory.db。

## 测试
全部 13 个原有/合并测试入口通过：124 个 unittest 测试加 smoke_test。
覆盖 UI 基础、Companion Core、Companion Loop、pending action 创建/审核/取消/延期/过期、Provider 切换与请求、Vision 请求与错误处理、Memory、Relationship、Temporal Context、聊天稳定性。
Python 编译检查通过。
真实 GUI 创建、事件处理、版本标题、后台循环接入与一次 Windows 活动状态采集通过（测试窗口立即隐藏并关闭）。
测试禁止联网，并使用临时数据库、设置和 UI 偏好。

## 已知问题与本地验收
DeepSeek/Ollama 的真实服务响应和真实图片识别未联网验证，需要用户本地配置与验收。
UI 文件校验保证设计保留，但仍需用户在自己的屏幕、缩放和字体环境下验收显示效果。
本机沙箱 Python 的 CustomTkinter 字体存在警告；在系统 Python 中完成真实启动检查通过。
真正主动发送消息属于 V1.7。本版本仅创建、复核、延期或取消候选行为。
现有 UI 调试入口保持不变；新循环可由 直接调用 controller.companion_loop.tick 获取调试快照，未增加页面。

## 打包
排除 .env、.git、.venv、数据库、聊天记录、日志、缓存、运行设置和私人数据。不上传 GitHub。
