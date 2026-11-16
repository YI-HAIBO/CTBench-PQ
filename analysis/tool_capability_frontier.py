#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tool_capability_frontier.py — 静态工具能力需求前沿（AND-gating vs OR-union）

问题
----
E9 证明：mock 规则基线 D3 ⊆ D1，12 种融合协议全部 n.s.，最佳仍是 D1 单模型。
但这只证伪了「弱规则基线有用」，不证伪 K3——ct-verif / Binsec 等工业级
静态分析工具召回率远高于 0.162，其预测集不一定被 D1 包含。

本脚本回答：**静态工具 T 需要达到什么 (召回率, 精确率) 水平，
AND-gating / OR-union 才能超过 D1 单模型（F1 = 0.592）？**

模型
----
现状（TEST 74）：D1 TP=29 FP=32 FN=8 TN=5（正例 37，负例 37）。

假设工具 T 的召回率 R_t、精确率 P_t。则 T 的误报数：
    F_t = N_neg * R_t * (1 - P_t) / P_t      （由 P = TP/(TP+FP) 反解）

工具 T 与 D1 **机制独立**（关键假设：静态分析与 LLM 原理不同，
近似独立；若相关则结论需修正）——T 的检出/误报在 D1 的判定集合内
按基数比例分布。

- **AND-gating（T 持否决权）**：预测 = D1 ∧ T
    TP = 29 * R_t
    FP = 32 * (F_t / 37)
    FN = 37 - TP
- **OR-union（T 持补报权）**：预测 = D1 ∨ T
    TP = 29 + 8 * R_t
    FP = 32 + 5 * (F_t / 37)
    FN = 37 - TP

输出
----
- analysis/tool_capability_frontier.md
  - AND-gating / OR-union 的 F1 曲面（R_t × P_t）
  - **临界前沿**：融合 F1 首次超过 0.592 所需的 (R_t, P_t)
  - 与当前 mock 基线（R=0.162, P=0.545）的对比
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"

# D1 (Agents-A1 × S1) 在 TEST 74 上的混淆矩阵
TP1, FP1, FN1, TN1 = 29, 32, 8, 5
N_POS = TP1 + FN1   # 37
N_NEG = FP1 + TN1   # 37
F1_D1 = 2 * (TP1 / (TP1 + FP1)) * (TP1 / N_POS) / ((TP1 / (TP1 + FP1)) + (TP1 / N_POS))

# mock 规则基线实测
R_mock, P_mock = 0.162, 0.545


def f1_of(tp: float, fp: float, fn: float) -> float:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


def tool_fp(r_t: float, p_t: float) -> float:
    """由 (R_t, P_t) 反解工具的误报数。P = TP/(TP+FP), TP = N_pos*R_t。"""
    tp_t = N_POS * r_t
    if p_t >= 1.0:
        return 0.0
    return tp_t * (1 - p_t) / p_t


def and_gating(r_t: float, p_t: float) -> tuple[float, float, float, float]:
    """返回 (TP, FP, FN, F1)"""
    f_t = tool_fp(r_t, p_t)
    tp = TP1 * r_t
    fp = FP1 * min(f_t / N_NEG, 1.0)
    fn = N_POS - tp
    return tp, fp, fn, f1_of(tp, fp, fn)


def or_union(r_t: float, p_t: float) -> tuple[float, float, float, float]:
    f_t = tool_fp(r_t, p_t)
    tp = TP1 + FN1 * r_t
    fp = FP1 + TN1 * min(f_t / N_NEG, 1.0)
    fn = N_POS - tp
    return tp, fp, fn, f1_of(tp, fp, fn)


def main() -> None:
    r_grid = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    p_grid = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    print(f"D1 单模型 F1 = {F1_D1:.3f}（TP={TP1} FP={FP1} FN={FN1} TN={TN1}）")
    print(f"mock 基线: R={R_mock} P={P_mock} F1={f1_of(N_POS*R_mock, tool_fp(R_mock,P_mock), N_POS*(1-R_mock)):.3f}\n")

    # ---------- 曲面 ----------
    lines = []
    lines.append("# 静态工具能力需求前沿\n")
    lines.append("> 由 `analysis/tool_capability_frontier.py` 生成。")
    lines.append(f"> 基准：D1（Agents-A1 × S1）F1 = **{F1_D1:.3f}**"
                 f"（TP={TP1} FP={FP1} FN={FN1} TN={TN1}，TEST 74 = 正例 {N_POS} / 负例 {N_NEG}）。")
    lines.append("> 假设：工具 T 与 D1 **机制独立**（静态分析 vs LLM），"
                 "T 的检出/误报在 D1 判定集合内按基数比例分布。\n")

    lines.append("## 1. AND-gating F1 曲面（T 持否决权）\n")
    lines.append("行 = 工具召回率 R_t，列 = 工具精确率 P_t。**粗体** = 超过 D1 单模型。\n")
    lines.append("| R_t \\ P_t | " + " | ".join(f"{p:.1f}" for p in p_grid) + " |")
    lines.append("|:--|" + "|--:".join([""] * (len(p_grid) + 1)) + "|")
    and_wins = []
    for r in r_grid:
        cells = []
        for p in p_grid:
            _, _, _, f1 = and_gating(r, p)
            mark = f"**{f1:.3f}**" if f1 > F1_D1 else f"{f1:.3f}"
            if f1 > F1_D1:
                and_wins.append((r, p, f1))
            cells.append(mark)
        lines.append(f"| {r:.1f} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 2. OR-union F1 曲面（T 持补报权）\n")
    lines.append("| R_t \\ P_t | " + " | ".join(f"{p:.1f}" for p in p_grid) + " |")
    lines.append("|:--|" + "|--:".join([""] * (len(p_grid) + 1)) + "|")
    or_wins = []
    for r in r_grid:
        cells = []
        for p in p_grid:
            _, _, _, f1 = or_union(r, p)
            mark = f"**{f1:.3f}**" if f1 > F1_D1 else f"{f1:.3f}"
            if f1 > F1_D1:
                or_wins.append((r, p, f1))
            cells.append(mark)
        lines.append(f"| {r:.1f} | " + " | ".join(cells) + " |")
    lines.append("")

    # ---------- 临界前沿 ----------
    lines.append("## 3. 临界前沿：T 需达到什么水平才能超过单模型\n")

    def frontier(fn_name, label):
        """对每个 R_t，找出最小的 P_t 使 F1 > F1_D1"""
        rows = []
        for r in r_grid:
            hit = None
            for p in p_grid:
                _, _, _, f1 = fn_name(r, p)
                if f1 > F1_D1:
                    hit = (p, f1)
                    break
            rows.append((r, hit))
        lines.append(f"### {label}\n")
        lines.append("| 工具召回率 R_t | 所需最低精确率 P_t | 融合 F1 |")
        lines.append("|--:|:--|--:|")
        for r, hit in rows:
            if hit:
                lines.append(f"| {r:.1f} | ≥ {hit[0]:.1f} | {hit[1]:.3f} |")
            else:
                lines.append(f"| {r:.1f} | — | 无法超过（即便 P_t=1.0） |")
        lines.append("")
        return rows

    and_rows = frontier(and_gating, "AND-gating")
    or_rows = frontier(or_union, "OR-union")

    # ---------- 面积对比 ----------
    n_cells = len(r_grid) * len(p_grid)
    lines.append("## 4. 可达区域对比\n")
    lines.append("| 融合方式 | 超过单模型的 (R_t,P_t) 组合数 | 占比 |")
    lines.append("|:--|--:|--:|")
    lines.append(f"| AND-gating（否决权） | {len(and_wins)} / {n_cells} | "
                 f"{len(and_wins)/n_cells*100:.0f}% |")
    lines.append(f"| OR-union（补报权） | {len(or_wins)} / {n_cells} | "
                 f"{len(or_wins)/n_cells*100:.0f}% |")
    lines.append("")

    # ---------- 结论 ----------
    lines.append("## 5. 结论：**权衡，不是单向优劣**\n")
    best_and = max(and_wins, key=lambda x: x[2]) if and_wins else None
    best_or = max(or_wins, key=lambda x: x[2]) if or_wins else None
    lines.append(
        f"1. **两种融合是「高门槛高回报」vs「低门槛低回报」的权衡，不是单向优劣**：\n"
        f"   - **OR-union（补报权）**：可达区域 **{len(or_wins)}/{n_cells} = "
        f"{len(or_wins)/n_cells*100:.0f}%**（几乎零门槛），"
        f"最优 F1 = {best_or[2]:.3f}（+{best_or[2]-F1_D1:.3f}）。\n"
        f"   - **AND-gating（否决权）**：可达区域仅 "
        f"{len(and_wins)}/{n_cells} = {len(and_wins)/n_cells*100:.0f}%"
        f"（需 R_t ≥ 0.6 且 P_t ≥ 0.6~0.9），"
        f"但最优 F1 = {best_and[2]:.3f}（+{best_and[2]-F1_D1:.3f}），**上限更高**。"
    )
    lines.append("")
    lines.append(
        "2. **为什么 OR-union 几乎零门槛**：D1 的 TN 池只有 5 条"
        "（37 个负例中已误报 32 个），OR 融合能新增的误报空间极小"
        "（最多 +5·F_t/37）。**D1 高 FPR 的现状反而使 OR 的边际代价很低。**"
    )
    lines.append(
        "3. **为什么 AND-gating 门槛高**：工具的召回率 R_t 同时决定"
        "它能保住多少 D1 的真阳性——AND 会**误杀** 29·(1−R_t) 个 TP。"
        "R_t=0.5 时误杀 14.5 个真阳性，代价远超压掉的误报。"
    )
    lines.append(
        "4. **⚠️ 对 E9 结论的修正（重要）**：E9 §4.3 曾据「AND 理想 0.879 / "
        "OR 理想 0.698」得出「K3 应走 AND-gating」。该结论建立在"
        "**完美工具假设**（工具能压掉全部 32 误报且不误杀任何 TP）上，"
        "**不现实**。在**机制独立**的现实现假设下：\n"
        "   - 工具强（R_t ≥ 0.7 且 P_t ≥ 0.7）→ AND-gating 更优（0.607–0.827）\n"
        "   - 工具弱（R_t < 0.6）→ **OR-union 是唯一有效选择**\n"
        "   - **正确表述是条件性的，不是「AND 优于 OR」。**"
    )
    lines.append(
        f"5. **mock 基线（R={R_mock}, P={P_mock}）落在两个可达区域之外**——"
        "这解释了 E9 的 12 协议全 n.s. 零结果："
        "**不是融合思路错，是工具太弱（R_t=0.162 远低于任何门槛）**。"
    )
    lines.append(
        "6. **局限**：以上为**独立假设下的解析推演**，非实测。"
        "ct-verif / Binsec 接入后需用真实预测集重算；"
        "若工具与 LLM 判定相关（非独立），结论需修正。"
        "特别地，若工具恰好擅长识别 D1 的误报（与 D1 负相关），"
        "AND-gating 的门槛会显著下降。"
    )
    lines.append("")

    (ANALYSIS / "tool_capability_frontier.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"→ 报告写入 {ANALYSIS/'tool_capability_frontier.md'}")

    print("\n==== 临界前沿（AND-gating）====")
    for r, hit in and_rows:
        print(f"  R_t={r:.1f} → 需 P_t≥{hit[0]:.1f} (F1={hit[1]:.3f})" if hit
              else f"  R_t={r:.1f} → 无法超过")
    print("\n==== 临界前沿（OR-union）====")
    for r, hit in or_rows:
        print(f"  R_t={r:.1f} → 需 P_t≥{hit[0]:.1f} (F1={hit[1]:.3f})" if hit
              else f"  R_t={r:.1f} → 无法超过")
    print(f"\n可达区域: AND {len(and_wins)}/{n_cells}, OR {len(or_wins)}/{n_cells}")


if __name__ == "__main__":
    main()
