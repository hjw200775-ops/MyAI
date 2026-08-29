# MyAI V1.3（第一阶段）

本版在 V1.2 基础上增加图片选择、发送前预览与取消、纯图片/纯文字/文字加图片消息，以及可替换的 Vision Provider。多会话、会话管理、静态头像、长期记忆、情绪、关系和 Context 架构均保留。

## 配置

把 `.env.example` 复制为 `.env`，只在本机填写真实 Key。不要把 `.env` 上传、截图或提交。

```env
DEEPSEEK_API_KEY=你的_DeepSeek_Key
MYAI_LLM_PROVIDER=deepseek
DEEPSEEK_MODEL=deepseek-v4-flash

MYAI_VISION_PROVIDER=openai
OPENAI_API_KEY=你的_OpenAI_Key
OPENAI_VISION_MODEL=gpt-5.4-mini
```

DeepSeek V4 Flash 处理纯文字消息、标题、记忆和状态分析。官方接口目前不支持真实图片输入，因此含图片消息仍交给独立的 OpenAI Vision Provider。如果没有配置 Vision Provider，纯文字仍可正常工作，图片消息会明确提示“尚未配置图片理解服务”。以后可在 `llm/` 中加入其他云端或本地视觉 Provider，不需要修改 `gui.py` 或写死到 `ai.py`。

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
  openai_vision.py     可替换的第一版 Vision Provider
  config.py            环境变量配置
memory.py              兼容迁移与最小图片历史支持
```

## 基础检查

```powershell
python -m compileall -q .
python tests\smoke_test.py
```

测试使用假的离线 Provider，不发起网络请求，也不读取或打印真实 `.env` Key。

