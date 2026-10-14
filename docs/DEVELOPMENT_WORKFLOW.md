# MyAI 开发与发布工作流

本文档记录 MyAI 仓库的日常开发、测试与发布约定。目标只有一个：**让每次发布都可复现，并且永远不再把密钥打进包里。**

---

## 1. 仓库结构

```text
MyAI/
├── core/          Companion 核心（状态、时间感知、决策、运行时、事件）
├── ui/            界面层（CustomTkinter；MainWindow / ChatView / MessageBubble ...）
├── llm/           Provider 层（DeepSeek / Ollama / Vision）
├── tests/         离线测试（模拟 Provider，禁止联网）
├── scripts/       工程脚本（build_release.py 发布打包）
├── docs/          设计文档与发布/验证报告
├── assets/        资源（角色立绘等）
│
├── ai.py                 对话流程
├── memory.py             长期记忆
├── settings.py           用户偏好持久化
├── companion_loop.py     Companion 循环（DecisionEngine / ActionReviewer）
├── companion_events.py   共同经历事件（数据库）
├── user_activity.py      用户活动采样
├── gui.py                唯一入口（只调用 ui.app.run()）
├── README.md / CHANGELOG.md / LICENSE / requirements.txt / .env.example
```

内部工程产物（合并报告、文件清单、验收记录）统一放 `docs/`，**不要留在仓库根目录**，保持根目录干净。

---

## 2. 分支与提交

- 只有一个长期分支：`main`。当前没有 PR 流程，直接提交到 `main`。
- **禁止 `force push`，禁止重写历史。** 新工作一律以追加提交的方式落在 `main` 上。
- 提交信息用约定式前缀：

| 前缀 | 用途 | 示例 |
|---|---|---|
| `feat:` | 版本发布 / 新能力 | `feat: release MyAI V1.6.2 Companion Loop` |
| `docs:` | 文档、许可证 | `docs: add MIT license and document Ollama environment variables` |
| `chore:` | 仓库维护、工具链 | `chore: prepare MyAI V1.6.2 release` |

---

## 3. 版本号来源

版本号没有集中常量，以这两处为准，改版本时必须同步：

1. `ui/main_window.py` 的 `WINDOW_TITLE`（例如 `"MyAI V1.6.2 Stable"`）—— `build_release.py` 就是从这里推断版本号的。
2. `CHANGELOG.md` 顶部最新的 `## [x.y.z]` 章节。

`README.md` 的「当前版本」与 Roadmap 表格也要同步。

---

## 4. 日常开发流程

```bash
# 1) 改代码（不要动无关文件）
# 2) 语法自检
python -m compileall -q .

# 3) 跑离线测试（必须带目标测试文件，见下一节）
python tests/run_offline.py tests/foundations_test.py

# 4) 确认没有敏感文件混进来
git status --short

# 5) 提交
git add -A
git commit -m "feat: ..."
git push origin main
```

提交前务必检查 `git status` 输出里没有 `.env`、`*.db`、`.venv/`、`__pycache__/`。

---

## 5. 测试

全部测试使用模拟 Provider / HTTP，**不需要也不允许**访问真实 DeepSeek 或 Ollama 服务。

`tests/run_offline.py` 是隔离入口：在导入测试前把 `socket.socket.connect` 与 `socket.create_connection` 替换为抛异常，并把数据库、数据目录、settings 指向临时目录。

> **注意**：`run_offline.py` **需要一个目标测试文件作为参数**（`target = sys.argv[1]`）。直接运行 `python tests/run_offline.py` 会 `IndexError`，这不是 bug。

运行全部测试入口：

```bash
for t in tests/*_test.py; do python tests/run_offline.py "$t" || echo "FAIL $t"; done
```

现有 13 个测试入口：

```text
companion_core_test.py      companion_test.py           deepseek_provider_test.py
foundations_test.py         latency_regression_test.py  ollama_provider_test.py
settings_test.py            smoke_test.py               stability_test.py
temporal_test.py            title_resilience_test.py    ui_foundation_test.py
vision_regression_test.py
```

---

## 6. 敏感信息政策

**这是本项目最重要的一条纪律。**

- 仓库里**只允许**存在 `.env.example`（占位符模板）。真实 `.env` 由使用者本地创建。
- **绝对不提交**：`.env` / `.env.*`、`*.db` / `*.sqlite*`、`.venv/`、`__pycache__/`、`*.pyc`、`logs/`、`cache/`、`memory.db`、`settings.json`。
- 上述规则同时写在 `.gitignore` 和 `scripts/build_release.py` 里，**两处都要维护**。
- 提交前自检：

```bash
git grep -nI -E "sk-[A-Za-z0-9]{24,}"      # 真实 API Key
git ls-files | grep -E "\.env$|\.db$|\.venv|__pycache__"   # 敏感文件名
git log --all -S "<疑似密钥>" --oneline     # 历史是否泄露过
```

### 历史教训（务必记住）

打包发布时**曾经两次**把真实 DeepSeek API Key 打进 zip：

| 版本 | 泄露位置 | 结果 |
|---|---|---|
| V1.6.1 | `.env.example` 内被填入真实 key | 提交前替换为占位符；未进入 Git |
| V1.6.2 | `.env` 被整份打包进 zip | 打包时排除；未进入 Git |

两次都靠人工检查拦住了，但**根本解法是第 7 节的打包脚本**，不要手工压缩目录。任何曾经进过 zip 的 key 都应视为已泄露并轮换。

---

## 7. 发布流程

### 7.1 用脚本打包（不要手工打包）

```bash
python scripts/build_release.py --list              # 只列清单 + 密钥扫描，不写 zip
python scripts/build_release.py                     # 生成 dist/MyAI_V<version>.zip
python scripts/build_release.py --version 1.6.2     # 显式指定版本号
```

脚本行为：

- 版本号从 `ui/main_window.py` 的 `WINDOW_TITLE` 推断，可用 `--version` 覆盖。
- 自动排除 `.env`、`.env.*`、`.venv`、`__pycache__`、`*.pyc`、`*.db`、`.git`、`logs`、`cache` 等（`.env.example` 例外保留）。
- **打包前对所有文本文件做密钥扫描；发现 `sk-...`、`ghp_...`、私钥块即中止，不生成 zip。**
- 产物写入 `dist/`（已被 `.gitignore` 忽略），顶层目录为单一的 `MyAI_V<version>/`。

### 7.2 创建 Tag 与 Release

```bash
git push origin main
gh release create v1.6.2 \
  --title "MyAI V1.6.2 - Companion Loop Foundation" \
  --notes-file <发布说明> \
  --target main
```

约定：

- Tag 名 `vX.Y.Z`；Release 标题 `MyAI VX.Y.Z - <代号>`。
- **Tag 必须指向具体的提交 sha，不要依赖分支名。** 若 `target_commitish` 留成 `main`，GitHub 会在**发布那一刻**才创建 tag，把分支当时的最新提交钉进去 —— 历史提交的发布就会错误地指向更新的代码。
- 发布旧版本时，用 `make_latest=false` 保护当前最新版本的 Latest 标记。
- 上传发布包：`gh release upload v1.6.2 dist/MyAI_V1.6.2.zip`

### 7.3 发布后检查

```bash
gh api repos/hjw200775-ops/MyAI/git/refs/tags          # tag 指向是否符合预期
gh api repos/hjw200775-ops/MyAI/releases/latest        # Latest 是否是目标版本
gh api repos/hjw200775-ops/MyAI/git/trees/main?recursive=1   # 远端文件清单
```

---

## 8. 禁止事项

- 修改源码逻辑来完成「整理」类任务（发布整理只动文档、脚本与配置）。
- `force push` 或任何形式的历史重写。
- 手工压缩目录生成发布包。
- 把 `.env`、数据库、虚拟环境、缓存、日志提交进仓库。
- 发布时留空 `target_commitish`（导致 tag 指向错误的提交）。

---

## 9. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `python tests/run_offline.py` 报 `IndexError` | 正常，它需要目标测试文件参数 |
| 脚本中文输出在控制台显示乱码 | Windows GBK 控制台的显示问题，不影响功能与产物；在 UTF-8 终端正常 |
| `git push` / `gh` 偶发超时 | 本机到 `github.com` 的连接不稳定（`api.github.com` 稳定得多）；重试即可，不要改用 force |
| `git show ":\.file"` 在 PowerShell 报错 | 反斜杠被转义，改用 `git show ":./file"` 或直接用 `Get-Content -Encoding utf8` |
| PowerShell 读中文文件出现乱码 | `Get-Content -Raw` 默认按系统 ANSI(GBK) 解码；读 UTF-8 文件请显式 `-Encoding utf8`，或用 Python 显式 UTF-8 |
