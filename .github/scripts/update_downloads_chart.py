#!/usr/bin/env python3
"""生成 yunTV Release 下载量图表。

流程:
  1. 从 GitHub Releases API 拉取全部 release 及其资产的下载量;
  2. 生成浅色/深色主题自适应的 SVG 图 (折线=累计下载量, 柱状=各版本下载量);
  3. 用时间戳参数刷新 README 里的图表引用, 避免图片缓存导致看不到最新数据。

用法:
    GITHUB_TOKEN=xxx python3 .github/scripts/update_downloads_chart.py
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

CST = timezone(timedelta(hours=8))
REPO_OWNER = os.environ.get("REPO_OWNER", "be-engineer")
REPO_NAME = os.environ.get("REPO_NAME", "yunTV")
API_ROOT = "https://api.github.com"

ROOT = Path(__file__).resolve().parents[2]
CHART_REL_PATH = "images/downloads-chart.svg"
CHART_PATH = ROOT / CHART_REL_PATH
README_PATH = ROOT / "README.md"

W, H = 900, 470
PLOT_LEFT, PLOT_RIGHT = 70, 876
LINE_TOP, LINE_BOTTOM = 110, 290
BAR_TOP, BAR_BOTTOM = 356, 404

STYLE = """
  text {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Hiragino Sans GB", "Microsoft YaHei", Roboto, Helvetica, Arial, sans-serif;
  }
  .t-title { fill: #1f2328; font-size: 20px; font-weight: 700; }
  .t-sub { fill: #59636e; font-size: 12px; }
  .t-panel { fill: #1f2328; font-size: 13px; font-weight: 600; }
  .t-axis { fill: #59636e; font-size: 10px; }
  .t-tag { fill: #1f2328; font-size: 10px; font-weight: 600; }
  .t-total { fill: #1f2328; font-size: 34px; font-weight: 700; }
  .t-label { fill: #59636e; font-size: 11px; }
  .t-val { fill: #0969da; font-size: 10.5px; font-weight: 600; }
  /* 用一层描边文字做光晕, 避免依赖 paint-order (部分渲染器不支持) */
  .t-halo { fill: none; stroke: #ffffff; stroke-width: 3px; stroke-linejoin: round; }
  .grid { stroke: #d1d9e0; stroke-width: 1; }
  .axis { stroke: #d1d9e0; stroke-width: 1; }
  .line { stroke: #f778ba; stroke-width: 2.5; fill: none; stroke-linejoin: round; stroke-linecap: round; }
  .dot { fill: #f778ba; stroke: #ffffff; stroke-width: 2; }
  .bar { fill: #f778ba; fill-opacity: 0.85; }
  @media (prefers-color-scheme: dark) {
    .t-title, .t-panel, .t-tag, .t-total { fill: #f0f6fc; }
    .t-sub, .t-axis, .t-label { fill: #9198a1; }
    .t-val { fill: #58a6ff; }
    .t-halo { stroke: #0d1117; }
    .grid, .axis { stroke: #30363d; }
    .dot { stroke: #0d1117; }
  }
"""


def api_get(path: str, token: str):
    req = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "yunTV-downloads-chart",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_releases(token: str) -> list[dict]:
    """返回按发布时间升序排列的 release 列表。"""
    releases: list[dict] = []
    for page in range(1, 11):
        batch = api_get(
            f"/repos/{REPO_OWNER}/{REPO_NAME}/releases?per_page=100&page={page}", token
        )
        if not batch:
            break
        for rel in batch:
            if rel.get("draft"):
                continue
            assets = rel.get("assets") or []
            published = rel.get("published_at") or rel.get("created_at")
            releases.append(
                {
                    "tag": rel.get("tag_name") or "",
                    "published": datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ"),
                    "downloads": sum(a.get("download_count", 0) for a in assets),
                    "assets": len(assets),
                }
            )
        if len(batch) < 100:
            break
    releases.sort(key=lambda r: r["published"])
    return releases


def nice_step(span: float, ticks: int = 4) -> float:
    if span <= 0:
        return 1.0
    raw = span / ticks
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def fmt_axis(v: float) -> str:
    if v >= 10000:
        text = f"{v / 10000:.1f}".rstrip("0").rstrip(".")
        return f"{text}万"
    return f"{int(v):,}"


def fmt_count(v: int) -> str:
    return f"{v:,}"


def build_svg(releases: list[dict], now: datetime) -> str:
    total = sum(r["downloads"] for r in releases)
    n = len(releases)
    cumulative: list[int] = []
    acc = 0
    for r in releases:
        acc += r["downloads"]
        cumulative.append(acc)

    parts: list[str] = []
    add = parts.append

    def value_text(x: float, y: float, text: str) -> None:
        """先描边一层做光晕, 再叠一层实心文字。"""
        add(f'<text class="t-halo" x="{x:.1f}" y="{y:.1f}" text-anchor="middle">{text}</text>')
        add(f'<text class="t-val" x="{x:.1f}" y="{y:.1f}" text-anchor="middle">{text}</text>')

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="yunTV Release 下载量趋势图">'
    )
    add("<title>yunTV Release 下载量趋势</title>")
    add(f"<style>{STYLE}</style>")
    add(
        '<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#f778ba" stop-opacity="0.35"/>'
        '<stop offset="100%" stop-color="#f778ba" stop-opacity="0"/>'
        "</linearGradient></defs>"
    )

    # ---- 头部: 标题 + 总下载量 ----
    add(f'<text class="t-title" x="24" y="40">yunTV Release 下载量</text>')
    subtitle = f"共 {n} 个版本 · {sum(r['assets'] for r in releases)} 个安装包 · 数据来自 GitHub Releases API"
    add(f'<text class="t-sub" x="24" y="60">{escape(subtitle)}</text>')
    add(f'<text class="t-label" x="{PLOT_RIGHT}" y="20" text-anchor="end">总下载量</text>')
    add(f'<text class="t-total" x="{PLOT_RIGHT}" y="52" text-anchor="end">{fmt_count(total)}</text>')

    if n == 0:
        add(f'<text class="t-axis" x="{W / 2}" y="200" text-anchor="middle">暂无 Release 数据</text>')
        add("</svg>")
        return "\n".join(parts)

    # ---- 面板一: 累计下载量折线 ----
    add(f'<text class="t-panel" x="24" y="96">累计下载量</text>')
    plot_h = LINE_BOTTOM - LINE_TOP
    plot_w = PLOT_RIGHT - PLOT_LEFT
    slot = plot_w / n

    step = nice_step(total, 4)
    tick = 0.0
    ticks: list[float] = []
    while tick <= total + step * 0.001:
        ticks.append(tick)
        tick += step
    if ticks[-1] < total:
        ticks.append(ticks[-1] + step)

    for t in ticks:
        y = LINE_BOTTOM - (t / total * plot_h if total else 0)
        add(
            f'<line class="grid" x1="{PLOT_LEFT}" y1="{y:.1f}" x2="{PLOT_RIGHT}" y2="{y:.1f}"'
            f'{" stroke-dasharray=\"3 3\"" if t else ""}/>'
        )
        add(f'<text class="t-axis" x="{PLOT_LEFT - 10}" y="{y + 3.5:.1f}" text-anchor="end">{fmt_axis(t)}</text>')

    xs = [PLOT_LEFT + slot * (i + 0.5) for i in range(n)]
    ys = [LINE_BOTTOM - (c / total * plot_h if total else 0) for c in cumulative]

    area_path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    area_path += f" L {xs[-1]:.1f} {LINE_BOTTOM} L {xs[0]:.1f} {LINE_BOTTOM} Z"
    add(f'<path d="{area_path}" fill="url(#area)"/>')

    line_path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in zip(xs, ys))
    add(f'<path class="line" d="{line_path}"/>')

    for x, y in zip(xs, ys):
        add(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')

    if n <= 12:
        for x, y, c in zip(xs, ys, cumulative):
            value_text(x, y - 11, fmt_count(c))

    # ---- 面板二: 各版本下载量柱状 ----
    add(f'<text class="t-panel" x="24" y="340">各版本下载量</text>')
    max_dl = max(r["downloads"] for r in releases) or 1
    bar_h = BAR_BOTTOM - BAR_TOP
    bar_w = min(52.0, slot * 0.5)
    label_every = 1 if slot >= 62 else int(math.ceil(62 / slot))

    for i, rel in enumerate(releases):
        x = xs[i]
        h = bar_h * (rel["downloads"] / max_dl)
        y = BAR_BOTTOM - h
        if h > 0:
            add(
                f'<rect class="bar" x="{x - bar_w / 2:.1f}" y="{y:.1f}" '
                f'width="{bar_w:.1f}" height="{max(h, 2):.1f}" rx="4"/>'
            )
            value_text(x, y - 6, fmt_count(rel["downloads"]))
        if i % label_every == 0 or i == n - 1:
            tag = rel["tag"] or "-"
            date = rel["published"].astimezone(CST).strftime("%m-%d")
            add(f'<text class="t-tag" x="{x:.1f}" y="422" text-anchor="middle">{escape(tag)}</text>')
            add(f'<text class="t-axis" x="{x:.1f}" y="436" text-anchor="middle">{date}</text>')

    # ---- 页脚 ----
    footer = f"更新于 {now.astimezone(CST):%Y-%m-%d}"
    add(f'<text class="t-axis" x="24" y="460">{footer}</text>')
    add(f'<text class="t-axis" x="{PLOT_RIGHT}" y="460" text-anchor="end">yuntv</text>')

    add("</svg>")
    return "\n".join(parts) + "\n"


def update_readme(version: str) -> bool:
    """刷新 README 中图表链接的时间戳参数, 返回是否有改动。"""
    if not README_PATH.exists():
        return False
    readme = README_PATH.read_text(encoding="utf-8")
    url = (
        f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/{CHART_REL_PATH}"
    )
    new_line = f"![yunTV 下载量趋势]({url}?v={version})"

    pattern = re.compile(r"!\[yunTV 下载量趋势\]\([^)]*\)")
    if pattern.search(readme):
        new_readme = pattern.sub(new_line.replace("\\", "\\\\"), readme)
    else:
        # 优先插到 "下载趋势" 小节标题后面, 否则插到徽章后面
        heading = re.compile(r"^#{2,4} .*下载.*趋势.*$", re.MULTILINE)
        match = heading.search(readme)
        if match:
            new_readme = (
                readme[: match.end()] + "\n\n" + new_line + readme[match.end():]
            ).lstrip("\n")
        else:
            anchor = re.compile(r"^!\[GitHub Downloads\]\([^)]*\)$", re.MULTILINE)
            if not anchor.search(readme):
                return False
            new_readme = anchor.sub(lambda m: m.group(0) + "\n\n" + new_line, readme, count=1)

    if new_readme == readme:
        return False
    README_PATH.write_text(new_readme, encoding="utf-8")
    return True


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("缺少 GITHUB_TOKEN / GH_TOKEN 环境变量", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    try:
        releases = fetch_releases(token)
    except urllib.error.HTTPError as exc:
        print(f"GitHub API 请求失败: {exc}", file=sys.stderr)
        return 1

    svg = build_svg(releases, now)
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)

    old_svg = CHART_PATH.read_text(encoding="utf-8") if CHART_PATH.exists() else ""
    changed = old_svg != svg
    if changed:
        CHART_PATH.write_text(svg, encoding="utf-8")
        print(f"已更新图表: {CHART_REL_PATH}")

    total = sum(r["downloads"] for r in releases)
    print(f"版本数 {len(releases)} · 总下载量 {total}")

    # 只有图表内容变化时才刷新 README 的缓存参数, 避免无意义的提交
    if changed:
        update_readme(now.strftime("%Y%m%d%H%M"))
    else:
        print("图表内容无变化, 跳过 README 更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
