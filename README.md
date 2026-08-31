# MyAI V1.3（第一阶段）

## 本次更新 · 2026-08-31

- **视觉模型切换**：默认使用 DeepSeek `deepseek-v4-flash-vision-exp`，与文字模型共用 DeepSeek API Key 和服务地址。
- **保持原有功能**：文字模型、GUI 分层、三类消息和历史图片路径持久化保留；base64 仅用于请求，不存数据库。
- **配置与测试完善**：新增配置模板和安全排除规则，补充离线回归测试；编译和 smoke test 已通过，真实 API 尚待本机验证。
- **升级提醒**：旧 `.env` 中的 `MYAI_VISION_PROVIDER` 需手动改为 `deepseek`，并新增 `DEEPSEEK_VISION_MODEL`；保留原数据库和图片目录。

完整修改文件清单与验证范围见 [CHANGELOG.md](CHANGELOG.md)。

本版在 V1.2 基础上增加图片选择、发送前预览与取消、纯图片/纯文字/文字加图片消息，以及可替换的 Vision Provider。多会话、会话管理、静态头像、长期记忆、情绪、关系和 Context 架构均保留。

## 配置

把 `.env.example` 复制为 `.env`，只在本机填写真实 Key。不要把 `.env` 上传、截图或提交。

```env
DEEPSEEK_API_KEY=你的_DeepSeek_Key
MYAI_LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-flash

DEEPSEEK_BASE_URL=https://api.deepseek.com
MYAI_VISION_PROVIDER=deepseek
DEEPSEEK_VISION_MODEL=deepseek-v4-flash-vision-exp
```

DeepSeek V4 Flash 继续处理无图片上下文的文字对话、标题、记忆和状态分析。含当前或历史图片的上下文默认交给独立的 DeepSeek Vision Provider，使用同一个 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`。两者的模型名独立，视觉模型默认为 `deepseek-v4-flash-vision-exp`。

视觉请求使用 OpenAI-compatible Chat Completions，user 消息包含 `text` 与 `image_url` 内容块。本地图片只在 Provider 发送请求时转成 base64 data URL，不改变原始上下文，也不将编码写入数据库。接口依据：[DeepSeek 官方图像理解文档](https://api-docs.deepseek.com/zh-cn/guides/vision/)。实验模型是否可调用仍取决于账号权限和服务可用性。

**从旧配置迁移：** 若已有 `MYAI_VISION_PROVIDER=openai` 或 `none`，需在本机手动改为 `deepseek`；新增 `DEEPSEEK_VISION_MODEL`，不要把文字模型名改成视觉模型。无需新增第二个 Key。程序不会覆盖现有配置。

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
```

测试使用假的离线 Provider，不发起网络请求，也不读取或打印真实 `.env` Key。


## 本地验收

1. 安装依赖后执行上方 compileall 和 smoke_test。smoke test 用临时数据库、生成的测试图片和模拟客户端，覆盖默认/后备/禁用配置、三类消息、真实 Provider 请求组装、历史图片恢复、图片缺失降级及数据库不存 base64；不发网络请求。
2. 仅在本机填写 `.env`，启动 `python gui.py`。新会话发送纯文字，确认正常回复；分别发送纯图片和文字加图片，确认模型能回答图中内容。
3. 关闭并重新打开程序，选回原会话，发送“再看一下之前的图片”。原图文件即使被移动，托管目录的图片仍应可用。当前 GUI 历史显示图片文件名占位，并非历史缩略图。
4. 本次离线检查不等同于真实 API 或 GUI 人工验收；账号权限、网络和实际识图质量需要步骤 2–3 验证。

交付包不包含 `.env`、聊天数据库或历史图片。更新原项目时请保留原数据库及图片目录，备份后覆盖源码；不要把交付包当作包含旧聊天数据的完整备份。
