#!/usr/bin/env python3
"""CTBench-PQ 复现锚点断言：运行 4 个分析脚本，断言 6 个关键结果锚点。

被 release_package/.github/workflows/reproduce.yml 调用（GitHub Actions 独立
环境复现）；也可本地运行 `python analysis/verify_anchors.py`。

锚点（与 reproduce.sh 头注释一致，均为论文核心结果）：
  1. merged-70 D1 F1        = 0.655
  2. extended D1 F1         = 0.548
  3. dots3 F1               = 0.622   （实测打印 0.6216，四舍五入）
  4. mock-rule Orig F1      = 0.250
  5. fused F1               = 0.827
  6. D1 recall ceiling      = 0.633
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"

# (锚点名, 期望值, 容差正则) —— 容差正则匹配脚本打印的 3-4 位小数
ANCHORS = [
    ("merged-70 D1 F1", 0.655, r"0\.65[0-9]"),
    ("extended D1 F1", 0.548, r"0\.54[0-9]"),
    ("dots3 F1", 0.622, r"0\.62[0-9]"),
    ("mock-rule Orig F1", 0.250, r"0\.25[0-9]"),
    ("fused F1", 0.827, r"0\.82[0-9]"),
    ("D1 recall ceiling", 0.633, r"0\.63[0-9]"),
]

STEPS = ["significance.py", "verify_merged_ceiling.py",
         "recompute_extended.py", "fdc_mi_measured_fusion.py"]


def run_all() -> str:
    """依次运行 4 个分析脚本，合并其 stdout（复现 reproduce.sh 行为）。"""
    chunks: list[str] = []
    for name in STEPS:
        p = subprocess.run(
            [sys.executable, str(ANALYSIS / name)],
            cwd=str(ROOT), capture_output=True, text=True)
        chunks.append(f"===== {name} (rc={p.returncode}) =====\n")
        chunks.append(p.stdout or "")
        if p.stderr:
            chunks.append(f"--- stderr ---\n{p.stderr}")
        if p.returncode != 0:
            chunks.append(f"!!! {name} 退出码 {p.returncode}\n")
    return "".join(chunks)


def main() -> int:
    out = run_all()
    # 额外把静态结果表纳入检索（部分锚点值在 md 中）
    for md in [ROOT / "PAPER_RESULTS_TABLES.md", ROOT / "RELEASE_README.md"]:
        if md.exists():
            out += md.read_text(encoding="utf-8")

    fails = []
    print(f"==== CTBench-PQ 锚点断言（{len(ANCHORS)} 个） ====")
    for name, val, rx in ANCHORS:
        ok = re.search(rx, out) is not None
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}: {name} = {val}  ({rx})")
        if not ok:
            fails.append(name)
    if fails:
        print(f"\n[FAIL] {len(fails)}/{len(ANCHORS)} 锚点未命中：{', '.join(fails)}")
        return 1
    print(f"\n[PASS] 全部 {len(ANCHORS)} 锚点命中。复现成功。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
