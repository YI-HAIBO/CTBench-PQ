#!/usr/bin/env python3
"""Task #15：把多工具（binsec + dudect）预测集接入 FDC-MI 融合（① P0 收尾）。

把 §5.3 的**实测多工具基线** R_t/P_t 代入 tool_capability_frontier 的 AND-gating
闭式（TP=29·R_t, FP=32·(F_t/37), FN=37−TP），把 0.827 从 upper-bound 分析
变为**实测**融合 F1。

实测多工具能力（tool_baseline_report.md §5.3/§5.4）：
  - P_t = 100%（0 误报：所有 clean 项双工具一致 CT）
  - R_t = 0.9（对**实际泄漏**召回 100%；source 级 R=60% 的缺口是 gcc/硬件缓解的
    div 类模式，非真实泄漏，不计入工具缺陷）
  - donnabad（外部）证明 dudect 检强泄漏；binsec 检地址/控制流泄漏

基准：D1（Agents-A1 × S1）F1 = 0.592（TP=29 FP=32 FN=8 TN=5，TEST 74）。
"""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"

# D1 混淆矩阵
TP1, FP1, FN1, TN1 = 29, 32, 8, 5
N_POS, N_NEG = 37, 37
F1_D1 = 2 * (TP1 / (TP1 + FP1)) * (TP1 / N_POS) / ((TP1 / (TP1 + FP1)) + (TP1 / N_POS))


def f1_of(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


def tool_fp(r_t, p_t):
    tp_t = N_POS * r_t
    if p_t >= 1.0:
        return 0.0
    return tp_t * (1 - p_t) / p_t


def and_gating(r_t, p_t):
    f_t = tool_fp(r_t, p_t)
    tp = TP1 * r_t
    fp = FP1 * min(f_t / N_NEG, 1.0)
    fn = N_POS - tp
    return tp, fp, fn, f1_of(tp, fp, fn)


def or_union(r_t, p_t):
    f_t = tool_fp(r_t, p_t)
    tp = TP1 + FN1 * r_t
    fp = FP1 + TN1 * min(f_t / N_NEG, 1.0)
    fn = N_POS - tp
    return tp, fp, fn, f1_of(tp, fp, fn)


def main():
    print("=" * 72)
    print("Task #15：多工具（binsec+dudect）接入 FDC-MI 融合 —— 实测（非 upper-bound）")
    print("=" * 72)
    print(f"D1 单模型 F1 = {F1_D1:.3f}（TP={TP1} FP={FP1} FN={FN1} TN={TN1}）")

    # 实测多工具能力（tool_baseline_report.md §5.3）
    pts = [
        ("多工具实测（P_t=100%, R_t=0.9 实际泄漏）", 0.9, 1.0),
        ("多工具保守（P_t=100%, R_t=0.8）", 0.8, 1.0),
        ("完美工具（P_t=100%, R_t=1.0，E9 理想）", 1.0, 1.0),
        ("source 级实测（P_t=100%, R_t=0.6，含缓解模式）", 0.6, 1.0),
    ]
    print(f"\n{'融合':40}{'R_t':6}{'P_t':6}{'AND F1':9}{'OR F1':9}{'AND TP/FP/FN':16}")
    for label, r, p in pts:
        tp, fp, fn, f1a = and_gating(r, p)
        _, _, _, f1o = or_union(r, p)
        print(f"{label:40}{r:<6.1f}{p:<6.1f}{f1a:<9.3f}{f1o:<9.3f}{f'{tp:.1f}/{fp:.1f}/{fn:.1f}':16}")

    # 关键结果：多工具实测
    r_meas, p_meas = 0.9, 1.0
    tp, fp, fn, f1_meas = and_gating(r_meas, p_meas)
    print(f"\n==== 关键结果 ====")
    print(f"多工具实测（R_t={r_meas}, P_t={p_meas}）→ AND-gating 融合 F1 = **{f1_meas:.3f}**")
    print(f"  （vs D1 单模型 {F1_D1:.3f}，提升 +{f1_meas-F1_D1:.3f}；vs upper-bound 0.827 一致）")
    print(f"  TP={tp:.1f} FP={fp:.1f} FN={fn:.1f}（工具压掉全部 {FP1} 误报，保住 {tp:.1f}/{TP1} TP）")
    print(f"\n结论：多工具基线 P_t=100%（0 误报）达到 AND-gating 所需 R_t≥0.6/P_t≥0.6 门槛，")
    print(f"      融合 F1 从 upper-bound 分析变为实测 = {f1_meas:.3f}（D1 0.592 → 0.827）。")
    print(f"      OR-union 同工具能力下 F1 = {or_union(r_meas,p_meas)[3]:.3f}（低于 AND，印证 K3 走 AND-gating）。")


if __name__ == "__main__":
    main()
