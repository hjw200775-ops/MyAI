# 小悠 UI Design Token

> 代码实现：`ui/theme.py`。本文件是跨平台（Desktop / Web / Live2D / 移动端）共用的设计规范，
> 修改 Token 时两处同步。所有值以这里为准，视图代码不得硬编码颜色、圆角、间距。

## 0. 设计关键词

日系 / 清爽 / 温柔 / 轻科技 / 桌面陪伴 / 极简 / 有生命感

视觉优先级：**角色 > 对话内容 > 功能按钮 > 系统信息**

禁止：大面积纯黑 + 高饱和霓虹、过多边框、大量渐变、过度玻璃拟态、粉色少女风、拥挤的信息面板。

## 1. 外观模式

| 模式 | 说明 |
|---|---|
| `dark`（默认） | 深灰蓝底，非纯黑 |
| `light` | 米白 / 灰蓝底 |
| `system` | 跟随操作系统 |

偏好保存在 `%APPDATA%\MyAI\ui_prefs.json`（`ui/ui_prefs.py`），与 `settings.json` 分离。

## 2. 颜色

所有 Token 均成对定义；CustomTkinter 通过 `ctk_color("token")` 取 `(light, dark)` 元组。

### 2.1 画布 / 表面

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `background` | `#F5F6FA` | `#17191F` | 窗口底色 |
| `surface` | `#FFFFFF` | `#20232B` | 卡片、面板、小悠气泡 |
| `surface_alt` | `#EEF0F5` | `#272B35` | 侧栏、输入区底、次级区域 |
| `surface_hover` | `#E8EAF1` | `#2D3240` | 可交互表面 hover |
| `surface_active` | `#E3E6F3` | `#32384A` | 当前选中项 |

### 2.2 强调色（低饱和蓝紫）

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `primary` | `#7B86C8` | `#8D97D6` | 发送按钮、当前导航、开关 ON |
| `primary_hover` | `#6A75B8` | `#9CA5E0` | 上述 hover |
| `primary_soft` | `#E9EBF8` | `#2E3350` | 用户气泡、选中态浅底 |
| `on_primary` | `#FFFFFF` | `#17191F` | primary 上的文字 / 图标 |

### 2.3 文字

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `text_primary` | `#2D3038` | `#E7E9EE` | 正文 |
| `text_secondary` | `#7A7F8C` | `#9AA0AE` | 次级说明、角色名旁标签 |
| `text_muted` | `#A3A8B5` | `#6E7482` | 占位符、时间戳、版本号 |
| `text_on_soft` | `#3B4160` | `#D6DAF2` | primary_soft 上的文字 |

### 2.4 线条

| Token | Light | Dark |
|---|---|---|
| `border` | `#E2E4EB` | `#2F333E` |
| `border_strong` | `#CDD1DC` | `#3C4150` |

边框只在必要处使用（输入框 focus、分隔线）；卡片默认靠底色区分，不描边。

### 2.5 聊天气泡

| Token | Light | Dark |
|---|---|---|
| `bubble_user` | `#E9EBF8` | `#2E3350` |
| `bubble_user_text` | `#2D3038` | `#E7E9EE` |
| `bubble_assistant` | `#EEF0F5` | `#272B35` |
| `bubble_assistant_text` | `#2D3038` | `#E7E9EE` |
| `bubble_system` | `#F0F1F5` | `#1F222A` |
| `bubble_system_text` | `#7A7F8C` | `#9AA0AE` |

### 2.6 语义状态

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `success` | `#6FB38A` | `#7FBF98` | 在线圆点、保存成功 |
| `warning` | `#D9A85B` | `#D9B36B` | 连接检查提示 |
| `error` | `#D47B7B` | `#D98A8A` | 删除、关闭按钮 hover、错误提示 |
| `error_hover` | `#C46A6A` | `#E09A9A` | |

### 2.7 其它

| Token | Light | Dark | 用途 |
|---|---|---|---|
| `scrollbar` | `#D5D8E2` | `#30343F` | |
| `scrollbar_hover` | `#BFC4D3` | `#3C4150` | |
| `titlebar` | `#F5F6FA` | `#17191F` | DWM 标题栏染色 + 内部视觉标题区 |
| `titlebar_text` | `#2D3038` | `#E7E9EE` | |
| `overlay` | `#000000` | `#000000` | 弹层遮罩（配合透明度） |

## 3. 圆角

| Token | px | 用途 |
|---|---|---|
| `xs` | 6 | 小组件：chip、标签、缩略图角标 |
| `sm` | 8 | 按钮、导航项 |
| `md` | 12 | 输入框、卡片 |
| `lg` | 14 | 聊天气泡 |
| `xl` | 16 | 弹窗、大气泡 |

## 4. 间距

只允许 `4 / 8 / 12 / 16 / 24 / 32`（Token：`xs / sm / md / lg / xl / xxl`）。

## 5. 尺寸

| Token | 值 | 说明 |
|---|---|---|
| `window_default` | 960 × 700 | |
| `window_min` | 780 × 580 | |
| `titlebar_height` | 44 | 内部视觉标题区 |
| `sidebar_width` | 72 | 图标导航栏 |
| `conversation_panel_width` | 220 | 对话页第二列（可折叠） |
| `content_max` | 720 | 记忆 / 设置 / 视觉页内容最大宽度；超宽窗口里居中，不再拉满 |
| `nav_button` | 44 | 导航按钮边长 |
| `avatar_sm / md / lg` | 28 / 36 / 72 | 气泡旁 / 标题栏 / 侧栏底部 |
| `input_min_height / input_max_height` | 52 / 160 | 多行输入条最小 / 最大高度（含内边距） |
| `input_preview` | 72 × 48 | 待发送图片 chip 缩略图 |
| `send_button` | 36 | 圆形发送按钮 |
| `bubble_max_ratio` | 0.70 | 气泡最大宽度 = 聊天区宽 × 0.70。超宽窗口里聊天区仍会拉满，阅读宽度留到 Phase 8 |
| `thumbnail` | 160 × 112 | 图片预览上限；输入 chip 使用更小的 `input_preview` |
| `icon` | 20 | 导航 / 按钮图标 |

## 6. 字体

| 用途 | 字体 |
|---|---|
| 中文 | Microsoft YaHei UI |
| 英文 | Segoe UI（Tk 单字体族下由 YaHei UI 的拉丁字形承担） |
| 等宽 | Consolas |

字号：`xs 11 / sm 12 / md 14 / lg 16 / xl 20 / xxl 24`。

| 场景 | 字号 / 字重 |
|---|---|
| 角色名「小悠」（标题区） | xxl bold |
| 页面标题 | xl bold |
| 气泡正文、输入框 | md / lg regular |
| 气泡上方名称标签 | sm regular，`text_secondary` |
| 时间戳、版本号 | xs，`text_muted` |

不引入未经许可的字体文件。

## 7. 动效

原则：少而自然。禁止弹跳、高频闪烁、粒子、RGB 光效。

| Token | ms | 场景 |
|---|---|---|
| `hover` | 120 | 按钮 / 导航 hover 底色过渡 |
| `fast` | 150 | 侧栏折叠 |
| `normal` | 200 | 页面切换 fade / slide |
| `slow` | 250 | 弹层出现 |
| `message_in` | 180 | 新消息 fade + 上浮 |
| `thinking_period` | 900 | 「小悠正在想……」三点呼吸一个周期 |
| `frame_interval` | 16 | after() 步进 |

Tk 没有 widget 级透明度：fade 用前景 / 背景色插值模拟；上浮用 pady 递减模拟。

## 8. 角色化文案

状态（左下角）：

| key | 文案 |
|---|---|
| `online` | ● 小悠在线 |
| `thinking` | ◐ 思考中 |
| `waiting` | ◌ 等待 |
| `resting` | ☾ 休息 |
| `proactive` | ✦ 主动思考 |

Thinking：

| key | 文案 |
|---|---|
| `default` | 小悠正在想…… |
| `vision` | 小悠正在看图片…… |
| `memory` | 小悠正在回忆…… |
| `screen` | 小悠正在看看屏幕…… |

主动消息标签：`小悠 · 刚刚想起你`。禁止出现 `API CONNECTED`、`AI主动消息` 等工程化描述。

输入框占位：`和小悠说点什么……`。Enter 发送，Shift+Enter 换行。Windows 上若 IME 仍在组字、按键码为 `VK_PROCESSKEY`，或 keysym 为 `Process`，Enter 只确认候选，不发送。候选确认后 0.25 秒内的下一次 Enter 也会被吃掉，避免输入法回放的回车被当成发送。组字检测失败时，确认候选的那一次 Enter 仍可能直接发送。

附件菜单目前只有「上传图片」。上传文件和截图未实现，不显示为可点击项。

## 9. 消息类型

| `MessageKind` | 来源 | 展示 |
|---|---|---|
| `USER` | DB `role='user'` | 右对齐，`bubble_user` |
| `ASSISTANT` | DB `role='assistant'` 或临时错误提示 | 左对齐，头像 28px + 「小悠」 |
| `PROACTIVE` | V1.7 预留 | 同 ASSISTANT，名称后加 `· 刚刚想起你` |
| `SYSTEM` | 不入库：「已记住」、问候占位 | 居中小字，`bubble_system` |

数据库 `messages.role` 仍只允许 `user / assistant`，PROACTIVE / SYSTEM 只存在于展示层。

记忆、设置、视觉页的内容宽度不超过 `content_max`（720）。主题只写入 `ui_prefs.json`。聊天顶栏只保留会话标题和 ModelSelector；完整的模型地址、连接检查在设置页。情绪和关系只在「角色状态 · 调试」里观察，不能在界面里改。视觉页只说明聊天内上传图片，不提供摄像头、截图或实时屏幕开关。

## 10. 窗口结构

```text
┌───────────────────────────────────────────────┐
│ ◯ 小悠  MyAI V1.6.1          (原生 ─ □ ×)     │  titlebar_height 44，DWM 染 titlebar 色
├──────┬────────────────────────────────────────┤
│ 💬   │ 会话列表(220，可折叠) │   对话区域      │
│ 🧠   │                       │                 │
│ 👁   │                       │                 │
│ ⚙    │                       │                 │
│      │                       │                 │
│ ◯    │                       │                 │
│ ●在线│                       │                 │
├──────┴───────────────────────┴────────────────┤
│  ＋        和小悠说点什么……              ➤     │  input 52–160
└───────────────────────────────────────────────┘
```

标题栏采用方案 A：保留 Windows 原生边框与按钮，`DwmSetWindowAttribute` 染色，窗口内部绘制视觉标题区；不使用 `overrideredirect`。

## 11. 分层

```text
UI (ui/)
├── theme / ui_prefs / models / assets          ← Phase 2
├── controller (ChatController)                 ← Phase 2
├── main_window / titlebar / sidebar            ← Phase 3
├── chat_view / message_bubble                  ← Phase 4
├── input_panel                                 ← Phase 5
├── pages / model_selector                          ← Phase 6
└── animations                                  ← Phase 7
        ↓ 只允许单向调用
Service: ai / memory / llm / settings / media / emotion / relationship / time_context
```

视图只与 `ChatController` 交互；业务模块不得 import `ui`。
