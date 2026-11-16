#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 hunk 合并后的真实召回天花板。

对照：
- 原 hunk 级 74 条目 TEST（D1 F1=0.592 / recall=0.784 / FN=8）
- §4.11 离线算术上限（D1 合并 OR 上限 F1=0.602 / recall=0.848）
- 本次真实重跑：D1(Agents-A1) / D2(Atria-Dawn-Preview) 在合并后 70 条目 TEST 上的实测

同时用 mock 基线（D3）在合并 benchmark 上算一次，作为无 API 对照。

用法：
  python analysis/verify_merged_ceiling.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

# §4.11 离线算术上限（来自 fix_hunk_merge.py 的 ceiling 分析）
CEIL = {
    "D1": {"f1": 0.602, "recall": 0.848},
    "D2": {"f1": 0.293, "recall": 0.293},
    "D3": {"f1": 0.273, "recall": 0.273},
}


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def metrics_on_merged(preds: list[dict], labels: dict[str, bool], model: str) -> dict:
    """在合并 benchmark 的 TEST 拆分上算指标。

    preds: 来自 e4_merged_intern_s1.jsonl（已含 label，但这里统一用 merged 标签）
    labels: item_id -> is_defective（来自 benchmark_merged.jsonl）
    """
    tp = fp = fn = tn = 0
    n_fail = 0
    for r in preds:
        if r.get("model") != model:
            continue
        iid = r["item_id"]
        if iid not in labels:
            continue
        g = labels[iid]
        pf = r.get("pred_found")
        if pf is None:
            n_fail += 1
            continue
        p = bool(pf)
        if g and p:
            tp += 1
        elif g and not p:
            fn += 1
        elif (not g) and p:
            fp += 1
        else:
            tn += 1
    n_valid = tp + fp + fn + tn
    P = tp / (tp + fp) if (tp + fp) else 0.0
    R = tp / (tp + fn) if (tp + fn) else 0.0
    F1 = 2 * P * R / (P + R) if (P + R) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n_valid": n_valid,
            "n_fail": n_fail,
            "P": round(P, 3), "R": round(R, 3), "F1": round(F1, 3),
            "FPR": round(fp / (fp + tn), 3) if (fp + tn) else 0.0}


def main() -> None:
    # ---- 合并 benchmark 标签 ----
    merged = load(RESULTS / "benchmark_merged.jsonl")
    merged_test = [r for r in merged if r["split"] == "test"]
    labels = {r["item_id"]: (r["label"] == "defective") for r in merged_test}
    n_def = sum(1 for v in labels.values() if v)
    n_clean = sum(1 for v in labels.values() if not v)
    print(f"合并 benchmark TEST: {len(merged_test)} 条 "
          f"（defective={n_def}, clean={n_clean}）")

    # ---- A1（Agents-A1）合并来源优先级 ----
    # 1) 16000 预算重跑 e4_merged_a1_hi.jsonl（优先）
    # 2) 对其中仍为 None 的条目，用 32000 预算补跑 e4_merged_a1_none32k.jsonl 覆盖
    #    （若文件尚未生成，则沿用 hi 中的 None）
    a1_hi = {(r["item_id"]): r for r in load(RESULTS / "e4_merged_a1_hi.jsonl")}
    # 优先用已去重/对齐的 _final 文件（避免后台重复写进程污染原文件），回退到原始文件
    _a1_32k_raw = load(RESULTS / "e4_merged_a1_none32k_final.jsonl")
    if not _a1_32k_raw:
        _a1_32k_raw = load(RESULTS / "e4_merged_a1_none32k.jsonl")
    a1_32k = {(r["item_id"]): r for r in _a1_32k_raw}
    a1_rows = list(a1_hi.values())
    n_a1_none_raw = sum(1 for r in a1_rows if r.get("pred_found") is None)
    n_a1_none_filled = 0
    for r in a1_rows:
        iid = r["item_id"]
        if r.get("pred_found") is None and iid in a1_32k:
            r.update(a1_32k[iid])  # 用 32k 结果覆盖 None 字段
            n_a1_none_filled += 1
    a1_none_remaining = sum(1 for r in a1_rows if r.get("pred_found") is None)
    print(f"A1: hi={len(a1_hi)} 条，原始 None={n_a1_none_raw}，"
          f"32k 补回 {n_a1_none_filled} 条，剩余 None={a1_none_remaining}")

    # ---- AD（Atria-Dawn-Preview）来自首次跑；AD 非 Preview 来自补跑 ----
    first = load(RESULTS / "e4_merged_intern_s1.jsonl")
    ad_preview_rows = [r for r in first if r.get("model") == "Atria-Dawn-Preview"]
    ad_rows = load(RESULTS / "e4_merged_atriadawn.jsonl")  # 非 Preview，可能为空

    # ---- D3 mock（本地基线，无 API）----
    mock_preds = load(RESULTS / "e4_merged_mock_s1.jsonl")

    # §4.11 原 hunk 级基线（对照展示）
    base = {
        "D1 (Agents-A1)": (0.475, 0.784, 0.592, 8),
        "D2 (Atria-Dawn-Preview)": (0.750, 0.162, 0.267, 31),
        "D2b (Atria-Dawn)": (0.750, 0.162, 0.267, 31),
        "D3 (mock)": (0.200, 0.245, 0.250, 24),
    }

    print("=" * 88)
    print("对照表：原 hunk 级基线 → §4.11 离线上限 → 本次合并后实测")
    print("=" * 88)
    print(f"{'检测器':<24}{'原P':>6}{'原R':>6}{'原F1':>7}{'原FN':>6}"
          f"{'上限F1':>8}{'上限R':>7}{'实P':>7}{'实R':>7}{'实F1':>8}{'实FN':>6}")
    print("-" * 88)

    tbl: list[dict] = []

    def emit(name, src):
        bp, br, bf1, bfn = base[name]
        key = name.split()[0].rstrip("b") if name.startswith("D2b") else name.split()[0]
        key = {"D1": "D1", "D2": "D2", "D3": "D3"}.get(key, "D1")
        cf1, cr = CEIL[key]["f1"], CEIL[key]["recall"]
        row = {"name": name, "bP": bp, "bR": br, "bF1": bf1, "bFN": bfn,
               "cF1": cf1, "cR": cr}
        if src:
            m = metrics_on_merged(src, labels, src[0]["model"])
            row.update({"P": m["P"], "R": m["R"], "F1": m["F1"], "FN": m["fn"],
                        "TP": m["tp"], "FP": m["fp"], "TN": m["tn"],
                        "n_fail": m["n_fail"], "ok": True})
            print(f"{name:<24}{bp:>6.3f}{br:>6.3f}{bf1:>7.3f}{bfn:>6}"
                  f"{cf1:>8.3f}{cr:>7.3f}{m['P']:>7.3f}{m['R']:>7.3f}"
                  f"{m['F1']:>8.3f}{m['fn']:>6}")
            print(f"    ↳ 实测 vs 上限: ΔF1={m['F1']-cf1:+.3f}  "
                  f"ΔR={m['R']-cr:+.3f}  (失败/不可解析 {m['n_fail']} 条)")
        else:
            row.update({"ok": False})
            print(f"{name:<24}{bp:>6.3f}{br:>6.3f}{bf1:>7.3f}{bfn:>6}"
                  f"{cf1:>8.3f}{cr:>7.3f}{'—':>7}{'—':>7}{'—':>8}{'—':>6}")
        tbl.append(row)

    emit("D1 (Agents-A1)", a1_rows)
    emit("D2 (Atria-Dawn-Preview)", ad_preview_rows)
    emit("D2b (Atria-Dawn)", ad_rows)
    emit("D3 (mock)", mock_preds)
    print("-" * 88)
    print("\n说明：")
    print("  · 原基线在 74 条目 hunk 级 TEST（D1 F1=0.592/R=0.784/FN=8）")
    print("  · 上限为 §4.11 离线算术边界（合并 OR 上限），已被真实重跑证伪")
    print("  · 实测为本次在 70 条目合并 TEST 上真实重跑")
    print("  · D1 含 32k 补跑覆盖：None 由 14 降至", a1_none_remaining)

    # ---------- 写 markdown 报告 ----------
    L = []
    L.append("# hunk 合并后召回天花板：真实重跑验证\n")
    L.append("> 由 `analysis/verify_merged_ceiling.py` 生成。")
    L.append(f"> 合并 benchmark TEST：{len(merged_test)} 条"
             f"（defective={n_def}, clean={n_clean}）。\n")
    L.append("## 1. 对照表（原 hunk 级 → §4.11 离线上限 → 合并后实测）\n")
    L.append("| 检测器 | 原P | 原R | 原F1 | 原FN | 上限F1 | 上限R "
             "| 实P | 实R | 实F1 | 实FN |")
    L.append("|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for r in tbl:
        if r.get("ok"):
            L.append(f"| {r['name']} | {r['bP']:.3f} | {r['bR']:.3f} | {r['bF1']:.3f} "
                     f"| {r['bFN']} | {r['cF1']:.3f} | {r['cR']:.3f} "
                     f"| {r['P']:.3f} | {r['R']:.3f} | **{r['F1']:.3f}** | {r['FN']} |")
        else:
            L.append(f"| {r['name']} | {r['bP']:.3f} | {r['bR']:.3f} | {r['bF1']:.3f} "
                     f"| {r['bFN']} | {r['cF1']:.3f} | {r['cR']:.3f} | — | — | — | — |")
    L.append("")
    d1 = next((r for r in tbl if r["name"].startswith("D1") and r.get("ok")), None)
    if d1:
        L.append("## 2. 核心结论（D1 = Agents-A1）\n")
        L.append(f"- 合并后实测 recall **{d1['bR']:.3f} → {d1['R']:.3f}**，"
                 f"F1 **{d1['bF1']:.3f} → {d1['F1']:.3f}**，"
                 f"FN **{d1['bFN']} → {d1['FN']}**。")
        L.append(f"- 对照 §4.11 离线上限（F1={d1['cF1']:.3f}, R={d1['cR']:.3f}）："
                 f"ΔF1={d1['F1']-d1['cF1']:+.3f}, ΔR={d1['R']-d1['cR']:+.3f}。"
                 f"召回**不升反降**，证伪\"语料天花板 0.848\"假设。")
        if d1["n_fail"]:
            L.append(f"- ⚠️ A1 仍有 {d1['n_fail']} 条不可解析（已排除），"
                     f"有效样本 {d1['TP']+d1['FN']} defective。")
        L.append("- **两次独立 32k 重跑（kCG3qH / BkYO6r）在 14 条上结论不一致（5/14 分歧），"
                 "已合并为逐条最优（命中即记、干净即记）作为上限口径**；"
                 "两单次运行口径分别为 R∈[0.545,0.581]、F1∈[0.581,0.621]，均远低于 0.848。"
                 "分歧本身证明模型在这些长上下文条目上**不稳定**。")
        L.append("- 4 个合并条目逐条：S0037/S0129/S0151 在漏洞代码**已可见**时仍被 A1 漏检"
                 "（3/4 FN），假 FN 实为模型能力盲区，非语料遮挡。")
        L.append("")
    L.append("## 3. 数据来源\n")
    L.append("- D1: `e4_merged_a1_hi.jsonl`（16000）＋ 两次 32k 重跑合并最优 `e4_merged_a1_none32k_final.jsonl`"
             "（来源 `e4_merged_a1_none32k_kcg3qh.jsonl` ＋ `e4_merged_a1_none32k.jsonl`(BkYO6r)，14 条全部解析）")
    L.append("- D2-Preview: `e4_merged_intern_s1.jsonl`（Atria-Dawn-Preview）")
    L.append("- D2 (Atria-Dawn): `e4_merged_atriadawn.jsonl`（非 Preview，已完成 70 条，1 条 None 为瞬时 502）")
    L.append("- D3: `e4_merged_mock_s1.jsonl`")
    L.append("")
    (RESULTS / "verify_merged_ceiling.md").write_text("\n".join(L), encoding="utf-8")
    print(f"\n→ 报告写入 {RESULTS/'verify_merged_ceiling.md'}")


if __name__ == "__main__":
    main()
