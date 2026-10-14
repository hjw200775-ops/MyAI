#!/usr/bin/env python3
"""MyAI 发布打包脚本。

生成可安全公开的发布 zip，自动排除密钥、虚拟环境、数据库、缓存与 Git 元数据，
并在打包前对所有文本文件做一次密钥扫描；发现疑似真实密钥即中止，不生成 zip。

用法::

    python scripts/build_release.py                  # 版本号从 WINDOW_TITLE 推断
    python scripts/build_release.py --version 1.6.2  # 显式指定
    python scripts/build_release.py --list           # 只列出会打包的文件，不写 zip
    python scripts/build_release.py --output D:/out/MyAI.zip

只用标准库，不联网。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

# --- 排除规则（目录名 / 文件名通配 / 后缀）-----------------------------------

# 任何层级下出现这些目录名即整棵剪掉
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "logs",
    "log",
    "cache",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "build",
    "dist",
    ".eggs",
}

# 这些后缀的文件一律不打包
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
}

# 精确文件名排除
EXCLUDE_NAMES = {
    ".env",
    ".DS_Store",
    "Thumbs.db",
    "settings.json",
    "memory.db",
}

# 例外：虽然形如 .env.*，但这是模板，必须打包
ALWAYS_INCLUDE = {
    ".env.example",
}

# 疑似真实密钥的模式（大小写敏感部分与含义见下）
SECRET_PATTERNS = [
    ("DeepSeek/OpenAI 风格 key", re.compile(r"sk-[A-Za-z0-9]{24,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# 判定为文本的后缀（做密钥扫描）；其余按二进制跳过扫描
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".env", ".example", ".js", ".ts", ".css", ".html", ".sh",
    ".cmd", ".bat", ".ps1", ".gitignore",
}

REPO_ROOT = Path(__file__).resolve().parents[1]


def detect_version(root: Path) -> str:
    """从 ui/main_window.py 的 WINDOW_TITLE 推断版本号。"""
    window = root / "ui" / "main_window.py"
    if window.is_file():
        text = window.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'WINDOW_TITLE\s*=\s*["\']MyAI\s+V?([0-9][0-9A-Za-z.\-]*)', text)
        if m:
            return m.group(1)
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        text = changelog.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^##\s*\[?([0-9][0-9A-Za-z.\-]*)", text, re.MULTILINE)
        if m:
            return m.group(1)
    raise SystemExit("无法推断版本号，请用 --version 指定")


def is_excluded(rel: Path) -> bool:
    """rel 是相对仓库根的路径。"""
    if rel.name in ALWAYS_INCLUDE:
        return False
    if rel.name in EXCLUDE_NAMES:
        return True
    # .env / .env.local / .env.production 等，但 .env.example 已在上面放行
    if rel.name == ".env" or rel.name.startswith(".env."):
        return True
    if rel.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def collect(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        # 原地剪枝，避免走进 .git / .venv 等大目录
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for name in sorted(filenames):
            full = here / name
            rel = full.relative_to(root)
            if is_excluded(rel):
                continue
            files.append(rel)
    return sorted(files, key=lambda p: p.as_posix())


def scan_secrets(root: Path, files: list[Path]) -> list[str]:
    """对所有文本文件做密钥扫描，返回问题描述列表。"""
    problems: list[str] = []
    for rel in files:
        if rel.suffix.lower() not in TEXT_SUFFIXES and rel.name not in TEXT_SUFFIXES:
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                snippet = m.group(0)[:16] + "..."
                problems.append(f"{rel.as_posix()}:{line}  [{label}]  {snippet}")
    return problems


def build(root: Path, version: str, output: Path | None, list_only: bool) -> int:
    files = collect(root)
    if not files:
        print("没有可打包的文件，异常。", file=sys.stderr)
        return 2

    total = sum((root / f).stat().st_size for f in files)

    print(f"MyAI 发布打包  version={version}")
    print(f"仓库根: {root}")
    print(f"文件数: {len(files)}    原始体积: {total / 1024 / 1024:.2f} MB")
    print("-" * 60)
    for rel in files:
        size = (root / rel).stat().st_size
        print(f"  {rel.as_posix():<58} {size:>9}")

    print("-" * 60)
    print("密钥扫描 ...")
    problems = scan_secrets(root, files)
    if problems:
        print("发现疑似真实密钥，已中止打包：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("请先清理这些内容，再重新运行。", file=sys.stderr)
        return 1
    print("  未发现疑似真实密钥")

    if list_only:
        print("--list 模式：未写出 zip")
        return 0

    if output is None:
        output = root / "dist" / f"MyAI_V{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    prefix = f"MyAI_V{version}"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in files:
            zf.write(root / rel, arcname=f"{prefix}/{rel.as_posix()}")

    print("-" * 60)
    print(f"已写出: {output}")
    print(f"zip 体积: {output.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"内含 {len(files)} 个文件，顶层目录 {prefix}/")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成 MyAI 发布 zip（自动排除敏感文件）")
    ap.add_argument("--version", help="版本号，默认从 ui/main_window.py 的 WINDOW_TITLE 推断")
    ap.add_argument("--output", help="输出 zip 路径，默认 dist/MyAI_V<version>.zip")
    ap.add_argument("--root", help="仓库根，默认本脚本的上级目录")
    ap.add_argument("--list", action="store_true", dest="list_only",
                    help="只列出会打包的文件并做密钥扫描，不写 zip")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else REPO_ROOT
    if not (root / "requirements.txt").is_file():
        print(f"警告: {root} 下没有 requirements.txt，可能不是 MyAI 仓库根", file=sys.stderr)

    version = args.version or detect_version(root)
    output = Path(args.output).resolve() if args.output else None

    return build(root, version, output, args.list_only)


if __name__ == "__main__":
    raise SystemExit(main())
