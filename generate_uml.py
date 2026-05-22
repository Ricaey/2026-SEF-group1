#!/usr/bin/env python3
"""
UML 图生成脚本（基于 Kroki API）

用法：
    # 从stdin读取PlantUML代码，输出到当前目录
    python generate_uml.py usecase_diagram < source.puml

    # 从文件读取，指定输出目录
    python generate_uml.py dfd_level0 --src uml_sources/dfd_level0.puml --dir .

    # 输出到 Typst 项目目录
    python generate_uml.py state_diagram --dir ./

说明：
    每次生成会同时：
    1. 将 PlantUML 源码保存到 uml_sources/<name>.puml（若--src指定文件则复制）
    2. 通过 Kroki API 生成 PNG，保存到 <dir>/<name>.png
"""

import argparse
import os
import sys
import requests
import shutil

KROKI_URL = "https://kroki.io/plantuml/png"
SOURCES_DIR = "uml_sources"


def ensure_sources_dir(base_dir: str) -> str:
    """确保 uml_sources 目录存在，返回其绝对路径"""
    path = os.path.join(base_dir, SOURCES_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def read_source(src_file: str | None) -> str:
    """读取 PlantUML 源码：优先从文件，否则从 stdin"""
    if src_file:
        with open(src_file, "r", encoding="utf-8") as f:
            return f.read()
    else:
        print("（等待 stdin 输入 PlantUML 代码，Ctrl+D 结束）", file=sys.stderr)
        return sys.stdin.read()


def save_source(source: str, sources_dir: str, name: str):
    """将 PlantUML 源码保存到 uml_sources/<name>.puml"""
    filepath = os.path.join(sources_dir, f"{name}.puml")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(source)
    print(f"源码已保存: {filepath}", file=sys.stderr)


def generate_png(source: str, output_path: str):
    """调用 Kroki API 生成 PNG"""
    resp = requests.post(
        KROKI_URL,
        data=source.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"Kroki 返回错误 (HTTP {resp.status_code})", file=sys.stderr)
        print(resp.content.decode("utf-8", errors="replace")[:500], file=sys.stderr)
        sys.exit(1)

    if resp.content[:4] != b"\x89PNG":
        print("Kroki 未返回有效的 PNG 图片", file=sys.stderr)
        print(resp.content[:200].decode("utf-8", errors="replace"), file=sys.stderr)
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(resp.content)
    print(f"图片已生成: {output_path} ({len(resp.content)} bytes)", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="生成 UML 图（PlantUML → PNG，基于 Kroki API）"
    )
    parser.add_argument("name", help="图表名称（不含扩展名）")
    parser.add_argument("--src", help="PlantUML 源码文件路径（不指定则从 stdin 读取）")
    parser.add_argument("--dir", default=".", help="PNG 输出目录（默认当前目录）")
    args = parser.parse_args()

    output_dir = os.path.abspath(args.dir)
    os.makedirs(output_dir, exist_ok=True)

    sources_dir = ensure_sources_dir(output_dir)

    source = read_source(args.src)
    if not source.strip():
        print("错误: 未提供 PlantUML 源码", file=sys.stderr)
        sys.exit(1)

    save_source(source, sources_dir, args.name)
    generate_png(source, os.path.join(output_dir, f"{args.name}.png"))


if __name__ == "__main__":
    main()
