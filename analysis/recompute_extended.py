#!/usr/bin/env python3
"""扩展 TEST（104 条）全检测器指标重算 + McNemar 精确检验。

D2 用 _v2 权威版（102 条）+ 2 条 PQC hard negative（D3-N0067/N0068，429 失败 None）
合并为 104 口径（e4_extended_Atria-Dawn-Preview_s1_v2_full.jsonl）。

读取 e4_extended_*_s1.jsonl 预测文件，计算：
  1. 各检测器 P/R/F1/TP/FP/FN/TN
  2. 全部检测器对的 McNemar 精确双侧检验
  3. 与 70 条口径的对比

用法：
  python analysis/recompute_extended.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results"

# ── 检测器文件映射 ──
# D1 重跑中断于 58/102，仍用原始全量基线；D2 用 11-04 全量重跑（_v2）。
# 非确定性（运行间翻转）见 extended_benchmark_results.md §8。
DETECTORS = {
    "D1 (Agents-A1)":         "e4_extended_Agents-A1_s1.jsonl",
    "D2 (Atria-Dawn-Preview)":"e4_extended_Atria-Dawn-Preview_s1_v2_full.jsonl",  # _v2 权威 102 条 + 2 条 PQC hard negative(None,429)
    "D2b (Atria-Dawn)":       "e4_extended_Atria-Dawn_s1.jsonl",  # 如果有
    "D3 (mock-rule-v1)":      "e4_extended_mock_s1.jsonl",
    "qwen3.8-27b":            "e4_extended_qwen3_8-27b_s1.jsonl",
    "deepseek-v4-flash":      "e4_extended_deepseek-v4-flash_s1.jsonl",
    "glm-5.3":                "e4_extended_glm-5_3_s1.jsonl",
    "intern-s2":              "e4_extended_intern-s2_s1.jsonl",
    "deepseek-v4-flash-vision":"e4_extended_deepseek-v4-flash-vision_s1.jsonl",
    "sensenova-6.8-flash-lite":"e4_extended_sensenova-6_8-flash-lite_s1.jsonl",
    "dots3-note-prev":        "e4_extended_dots3-note-prev_s1.jsonl",
    # ── L2 独立平台模型（2026-11-16 新增）──
    "agnes-3.0-flash":        "e4_extended_agnes-3_0-flash_s1.jsonl",
    "nex-n2.6":               "e4_extended_nex-n2_6_s1.jsonl",
}

# ── McNemar 精确双侧检验（符号检验二项）──
def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 精确双侧 p 值：n=b+c, k=min(b,c) 的二项尾概率×2。"""
    if b + c == 0:
        return 1.0
    n = b + c
    k = min(b, c)
    # 二项分布 P(X <= k) 双侧
    from math import comb
    p_one = sum(comb(n, i) * 0.5 ** n for i in range(0, k + 1))
    return min(1.0, 2 * p_one)


def load_preds(fname: str) -> list[dict]:
    fp = RESULTS / fname
    if not fp.exists():
        return []
    with open(fp, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def compute_metrics(rows: list[dict]) -> dict:
    # 非 CT 语义迁移噪音（non_ct_noise）退出评估：从当前 extended 基准读取噪音集合并跳过
    noise_ids = set()
    benchf = RESULTS / "benchmark_extended.jsonl"
    if benchf.exists():
        for l in benchf.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            it = json.loads(l)
            if it.get("non_ct_noise"):
                noise_ids.add(it["item_id"])
    tp = fp = fn = tn = 0
    n_fail = 0
    for r in rows:
        if r.get("item_id") in noise_ids:
            continue
        if r["pred_found"] is None:
            n_fail += 1
            continue
        gold = r["label"] == "defective"
        pred = bool(r["pred_found"])
        if gold and pred:
            tp += 1
        elif gold:
            fn += 1
        elif pred:
            fp += 1
        else:
            tn += 1
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"n": len(rows), "n_valid": tp + fp + fn + tn, "n_fail": n_fail,
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "P": round(prec, 4), "R": round(rec, 4), "F1": round(f1, 4)}


def main() -> None:
    print("=" * 80)
    print("扩展 TEST（104 条）全检测器指标 + McNemar")
    print("=" * 80)

    # ── 加载基准 GT ──
    bench = {}
    with open(RESULTS / "benchmark_extended.jsonl", encoding="utf-8") as f:
        for l in f:
            it = json.loads(l)
            if it["split"] == "test" and not it.get("non_ct_noise"):
                bench[it["item_id"]] = it
    print(f"TEST 基准: {len(bench)} 条 "
          f"({sum(1 for v in bench.values() if v['label']=='defective')} defective / "
          f"{sum(1 for v in bench.values() if v['label']=='clean')} clean)")

    # ── 各检测器指标 ──
    print("\n── 各检测器指标 ──")
    print(f"{'检测器':30s} {'n':>4s} {'有效':>4s} {'失败':>4s} {'P':>7s} {'R':>7s} {'F1':>7s} "
          f"{'TP':>4s} {'FP':>4s} {'FN':>4s} {'TN':>4s}")
    print("-" * 100)

    metrics: dict[str, dict] = {}
    preds: dict[str, dict[str, dict]] = {}  # name -> {item_id -> row}

    for name, fname in DETECTORS.items():
        rows = load_preds(fname)
        if not rows:
            continue
        m = compute_metrics(rows)
        metrics[name] = m
        preds[name] = {r["item_id"]: r for r in rows}
        print(f"{name:30s} {m['n']:4d} {m['n_valid']:4d} {m['n_fail']:4d} "
              f"{m['P']:7.4f} {m['R']:7.4f} {m['F1']:7.4f} "
              f"{m['TP']:4d} {m['FP']:4d} {m['FN']:4d} {m['TN']:4d}")

    if len(metrics) < 2:
        print("\n⚠️ 有效检测器不足 2 个，无法做 McNemar")
        return

    # ── McNemar 全对 ──
    print("\n── McNemar 精确双侧检验（扩展 TEST 104 条）──")
    print(f"{'对':45s} {'b':>4s} {'c':>4s} {'b+c':>4s} {'p':>10s} {'显著性':>6s}")
    print("-" * 85)

    results = []
    # 非 CT 噪音退出评估（McNemar 同步排除）
    noise_ids = set()
    benchf = RESULTS / "benchmark_extended.jsonl"
    if benchf.exists():
        for l in benchf.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            it = json.loads(l)
            if it.get("non_ct_noise"):
                noise_ids.add(it["item_id"])
    for (n1, p1), (n2, p2) in combinations(preds.items(), 2):
        # 配对：两个检测器都有有效预测（非 None）的样本
        b = c = 0  # b: n1+ n2-, c: n1- n2+
        for iid in set(p1) & set(p2):
            if iid in noise_ids:
                continue
            r1, r2 = p1[iid], p2[iid]
            if r1["pred_found"] is None or r2["pred_found"] is None:
                continue
            if r1["pred_found"] and not r2["pred_found"]:
                b += 1
            elif not r1["pred_found"] and r2["pred_found"]:
                c += 1
        p = mcnemar_exact(b, c)
        sig = "✅ p<.05" if p < 0.05 else "n.s."
        label = f"{n1} vs {n2}"
        print(f"{label:45s} {b:4d} {c:4d} {b+c:4d} {p:10.4f} {sig:>6s}")
        results.append({"pair": label, "b": b, "c": c, "p": p, "sig": p < 0.05})

    # ── 与 70 条口径对比 ──
    print("\n── 与 70 条合并口径对比（D1/D2/D3）──")
    old = {"D1 (Agents-A1)": (0.679, 0.594, 0.633),
           "D2 (Atria-Dawn-Preview)": (1.000, 0.121, 0.216),
           "D3 (mock-rule-v1)": (0.545, 0.182, 0.273)}
    for name, (op, orr, of1) in old.items():
        if name in metrics:
            m = metrics[name]
            print(f"{name:30s} 70条: P={op:.3f} R={orr:.3f} F1={of1:.3f}  →  "
                  f"102条: P={m['P']:.3f} R={m['R']:.3f} F1={m['F1']:.3f}  "
                  f"ΔF1={m['F1']-of1:+.3f}")

    # ── 汇总 ──
    n_sig = sum(1 for r in results if r["sig"])
    print(f"\n汇总: {len(results)} 对检验, {n_sig} 对显著 (p<0.05), {len(results)-n_sig} 对 n.s.")


if __name__ == "__main__":
    main()
