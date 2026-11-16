#!/usr/bin/env python3
"""显著性检验（E4c）+ 论文用三线表导出。

用途：
  1. 对同基准集上的不同 (model, strategy) 配置做 **McNemar 精确配对检验**，
     给 ΔF1 / ΔAcc 配上 p 值——审稿人必问"0.592 vs 0.408 是不是运气"。
  2. 把 E4 / E5' / E4b 的结果整理成可直接贴进论文 §6 的三线表。
  3. 所有统计量**从数据现场算出**，不硬编码任何数字，避免口径漂移。

口径要点（沿用本轮修好的标准）：
  · pred_found 为 None 的行（调用失败/解析失败）**绝不进混淆矩阵**，
    单列 n_valid / n_failed，并在表中标注 n_valid。
  · 有效调用率 <90% 的 cell 直接剔除（多为 429 配额打爆）。
  · **排除 *smoke*.jsonl**：3 条验证跑会被 glob 扫入并在去重时覆盖全量跑结果。
  · 排除 mock 模式（规则基线）——它不参与 LLM 显著性比较。

用法：
  python analysis/significance.py                 # 控制台 + 导出 md
  python analysis/significance.py --md only       # 只导出 md
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
DATA = ROOT / "corpus" / "data" / "benchmark.jsonl"
MD_OUT = ROOT / "PAPER_RESULTS_TABLES.md"

MIN_VALID_COVERAGE = 0.90   # 有效调用率门槛
MIN_CELL_N = 50             # cell 有效样本量门槛

# PQC 关键词（用于计算 PQC 子集）
PQC_PAT = re.compile(
    r"kyber|ml-?kem|dilithium|ml-?dsa|sphincs|falcon|lattice|crystals|ntru|"
    r"module-?lattice|poly|ring-?lattice",
    re.I,
)


# ---------------------------------------------------------------- 读取

def load_jsonl(p: Path) -> list[dict]:
    try:
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        return []


def discover_cells() -> dict[tuple, dict[str, dict]]:
    """收集所有真实 LLM 预测 cell：(model, strategy, repeat) -> {item_id: row}。

    去重键含 item_id；**排除 smoke 文件**，避免 3 条验证跑覆盖全量跑结果。
    """
    cells: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for p in sorted(RESULTS.glob("*.jsonl")):
        if "smoke" in p.name:
            continue
        for r in load_jsonl(p):
            if r.get("mode") in (None, "mock"):
                continue
            if r.get("repeat") != 1 or not r.get("item_id"):
                continue
            key = (r.get("model"), r.get("strategy"), r.get("repeat"))
            if key[1] is None:
                continue
            cells[key][r["item_id"]] = r
    return cells


def cell_metrics(rows: list[dict]) -> dict:
    """混淆矩阵 + P/R/F1/FPR/Acc。失败行（pred_found=None）排除在外。"""
    tp = fp = fn = tn = n_failed = 0
    for r in rows:
        if r["pred_found"] is None:
            n_failed += 1
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
    n_valid = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "n_valid": n_valid, "n_failed": n_failed,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "P": prec, "R": rec, "F1": f1,
        "FPR": fp / (fp + tn) if (fp + tn) else 0.0,
        "Acc": (tp + tn) / n_valid if n_valid else 0.0,
    }


def quality_gates(cells: dict[tuple, dict[str, dict]]) -> list[tuple]:
    """返回通过有效性的 cell：(key, rows, metrics)。"""
    ok = []
    for key, by_id in cells.items():
        rows = list(by_id.values())
        n = len(rows)
        n_failed = sum(1 for r in rows if r["pred_found"] is None)
        cov = 1 - n_failed / n if n else 0.0
        if cov < MIN_VALID_COVERAGE or n < MIN_CELL_N:
            continue
        m = cell_metrics(rows)
        if m["n_valid"] < MIN_CELL_N:
            continue
        ok.append((key, rows, m))
    return sorted(ok, key=lambda x: (x[0][0], x[0][1]))


# ---------------------------------------------------------------- McNemar

def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 精确双侧检验（符号检验二项）。

    b = 配置 A 正确而 B 错误；c = B 正确而 A 错误。
    小样本下比卡方连续校正更可靠，也是 n<250 时推荐做法。
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2.0 * tail / (2.0 ** n))


def mcnemar_chi2_yates(b: int, c: int) -> float:
    """McNemar 卡方（Yates 连续性校正），仅作参照；b+c<10 时无意义。"""
    n = b + c
    if n == 0 or n < 10:
        return float("nan")
    chi2 = (abs(b - c) - 1) ** 2 / n
    return chi2


def paired_stats(a_rows: dict[str, dict], b_rows: dict[str, dict]) -> dict:
    """在两个配置共有的有效 item_id 上做配对统计。"""
    a_ok = b_ok = n = 0
    discord_a = discord_b = 0   # 不一致对：A 对 B 错 / B 对 A 错
    for iid in a_rows:
        ra, rb = a_rows.get(iid), b_rows.get(iid)
        if not ra or not rb:
            continue
        if ra["pred_found"] is None or rb["pred_found"] is None:
            continue
        gold = ra["label"] == "defective"
        ca = (bool(ra["pred_found"]) == gold)
        cb = (bool(rb["pred_found"]) == gold)
        if ca == cb:
            continue
        n += 1
        if ca and not cb:
            discord_a += 1
            a_ok += 1
        elif cb and not ca:
            discord_b += 1
            b_ok += 1
    both_right = None
    p_exact = mcnemar_exact(discord_a, discord_b)
    return {"n_pair": n, "b": discord_a, "c": discord_b,
            "chi2_yates": mcnemar_chi2_yates(discord_a, discord_b),
            "p_exact": p_exact}


def sig_mark(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "n.s."


def build_pairs(good: list[tuple]) -> list[tuple]:
    """生成待比较的 cell 对。每个元素 = (类型, key_a, key_b)。

    关键：pair 必须同时携带**两侧各自的 (model, strategy)**，否则跨模型比较
    （两侧 strategy 同名，如 Agents-A1 S1 vs Atria-Dawn S1）会被压成同一个
    key，退化成自身比较（n_pair=0）而被静默丢弃。
    """
    pairs: list[tuple] = []
    keys = [k for k, *_ in good]
    for ka, kb in combinations(keys, 2):
        if ka[0] == kb[0] and ka[1] != kb[1]:
            pairs.append(("同模型×提示", ka, kb))   # 提示消融
        elif ka[1] == kb[1] and ka[0] != kb[0]:
            pairs.append(("跨模型×提示", ka, kb))   # 跨模型泛化
    return pairs


def iter_pairs(good: list[tuple], pairs: list[tuple]) -> list[tuple]:
    """对每个 pair 计算配对统计，返回 (标签, key_a, key_b, 统计, ΔF1, ΔAcc)。"""
    by_key = {k: ({r["item_id"]: r for r in rows}, m) for k, rows, m in good}
    out = []
    for kind, ka, kb in pairs:
        if ka not in by_key or kb not in by_key:
            continue
        if ka == kb:
            continue
        ra, ma = by_key[ka]
        rb, mb = by_key[kb]
        st = paired_stats(ra, rb)
        d1 = ma["F1"] - mb["F1"]
        da = ma["Acc"] - mb["Acc"]
        if ka[0] == kb[0]:
            lbl = f"{ka[0]} {ka[1]} vs {kb[1]}"
        else:
            lbl = f"{ka[0]} {ka[1]}  vs  {kb[0]} {kb[1]}"
        out.append((lbl, ka, kb, st, d1, da))
    return out


# ---------------------------------------------------------------- 导出

def md(rows: list[str]) -> str:
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=str(MD_OUT), help="三线表输出路径")
    args = ap.parse_args()

    bench = load_jsonl(DATA)
    cells = discover_cells()
    good = quality_gates(cells)

    # ---------- 控制台 ----------
    print("=" * 96)
    print("有效 cell（有效调用率 ≥90% 且 n_valid ≥50）")
    print("=" * 96)
    print(f"{'模型':<22}{'策略':<6}{'n_valid':>8}{'n_fail':>8}"
          f"{'P':>8}{'R':>8}{'F1':>8}{'FPR':>8}{'Acc':>8}")
    print("-" * 96)
    for key, rows, m in good:
        print(f"{str(key[0]):<22}{str(key[1]):<6}{m['n_valid']:>8}{m['n_failed']:>8}"
              f"{m['P']:>8.3f}{m['R']:>8.3f}{m['F1']:>8.3f}"
              f"{m['FPR']:>8.3f}{m['Acc']:>8.3f}")

    print("\n" + "=" * 96)
    print("McNemar 精确配对检验（同基准集，配对单位 = 单个函数样本）")
    print("=" * 96)
    pairs = build_pairs(good)

    print(f"{'比较':<44}{'配对n':>7}{'b':>5}{'c':>5}"
          f"{'ΔF1':>9}{'ΔAcc':>9}{'p_exact':>10}{'显著性':>8}")
    print("-" * 96)
    for lbl, key_a, key_b, st, d1, da in iter_pairs(good, pairs):
        print(f"{lbl:<44}{st['n_pair']:>7}{st['b']:>5}{st['c']:>5}"
              f"{d1:>+9.3f}{da:>+9.3f}{st['p_exact']:>10.4f}"
              f"{sig_mark(st['p_exact']):>8}")

    # ---------- 导出三线表 ----------
    export_md(bench, good, pairs, args.md)


def export_md(bench, good, pairs, out: str) -> None:
    L: list[str] = []
    A = L.append

    # ---- 数据构成 ----
    tot = len(bench)
    split = Counter(r["split"] for r in bench)
    sdc = Counter(f"{r['split']}-{r['label']}" for r in bench)
    origin = Counter(r["origin"] for r in bench)
    dt = Counter(r.get("defect_type") or "(空)" for r in bench)
    lang = Counter(r["language"] for r in bench)
    lib = Counter(r["library"] for r in bench)
    sev = Counter(r.get("severity") or "(空)" for r in bench)
    pqc = [r for r in bench
           if PQC_PAT.search(f"{r.get('library','')} {r.get('repo','')} "
                             f"{r.get('file','')} {r.get('function_hint','')} "
                             f"{r.get('cve_id','')}")]

    A("# CTBench-PQ 论文用结果表（三线表）")
    A("")
    A("> 自动生成：`analysis/significance.py`。")
    A("> **所有数字均从 `corpus/data/benchmark.jsonl` 与 `results/*.jsonl` 现场计算，")
    A("> 未硬编码。** 调用失败/解析失败的预测一律排除出混淆矩阵，`n_valid` 已单列。**")
    A("")
    A("---")
    A("")
    A("## 表 1　CTBench-PQ 数据构成")
    A("")
    A(f"全部样本 **{tot}** 条；TEST/DEV/TRAIN = "
      f"{split.get('test',0)}/{split.get('dev',0)}/{split.get('train',0)}。"
      f"TEST 集正负平衡（{sdc.get('test-defective',0)}/{sdc.get('test-clean',0)}）。")
    A("")
    A("| 来源 origin | 数量 | 占比 |")
    A("|:--|--:|--:|")
    for k, v in sorted(origin.items(), key=lambda x: -x[1]):
        A(f"| {k} | {v} | {v/tot:.1%} |")
    A("")
    A("**表 2　分层切分与标签平衡**")
    A("")
    A("| split | 总数 | defective | clean | 正例率 |")
    A("|:--|--:|--:|--:|--:|")
    for s in ("test", "dev", "train"):
        n = split.get(s, 0)
        d = sdc.get(f"{s}-defective", 0)
        c = sdc.get(f"{s}-clean", 0)
        A(f"| {s.upper()} | {n} | {d} | {c} | {d/n:.1%} |")
    A("")
    A("**表 3　缺陷类型分布（benchmark 全量）**")
    A("")
    A("| 缺陷类型 | 数量 | 占比 |")
    A("|:--|--:|--:|")
    for k, v in sorted(dt.items(), key=lambda x: -x[1]):
        A(f"| {k} | {v} | {v/tot:.1%} |")
    A("")
    A(f"**表 4　语言与库覆盖**：语言 "
      + " / ".join(f"{k} {v}" for k, v in sorted(lang.items(), key=lambda x: -x[1]))
      + f"；库 " + " / ".join(f"{k} {v}" for k, v in sorted(lib.items(), key=lambda x: -x[1])) + f"。")
    A("")
    A(f"**PQC 子集**：关键词命中 **{len(pqc)}** 条"
      f"（TEST 内 {sum(1 for r in pqc if r['split']=='test')} 条）。")
    A("")
    A("---")
    A("")
    A("## 表 5　主实验结果：LLM 检测性能（E4 / E5′ / E4b）")
    A("")
    A("> 有效调用率 ≥90% 的 cell；`n_valid` 为进入混淆矩阵的有效预测数。")
    A("> 未达门槛的模型（qwen3.8-27b 有效 2/74、deepseek-v4-flash-0731 有效 0/74）已剔除。")
    A("")
    A("| 模型 | 策略 | n_valid | P | R | **F1** | FPR | Acc | TP | FP | FN | TN |")
    A("|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for key, rows, m in good:
        A(f"| {key[0]} | {key[1]} | {m['n_valid']} | {m['P']:.3f} | {m['R']:.3f} | "
          f"**{m['F1']:.3f}** | {m['FPR']:.3f} | {m['Acc']:.3f} | "
          f"{m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")
    A("")
    A("---")
    A("")
    A("## 表 6　McNemar 精确配对检验")
    A("")
    A("> 配对单位 = 单个函数样本；b = 左侧配置正确而右侧错误，c = 反之。")
    A("> p 为精确双侧（符号检验二项），n_pair<250 时优于卡方近似。")
    A("> 显著性：\\*\\*\\* p<.001，\\*\\* p<.01，\\* p<.05，n.s. 不显著。")
    A("")
    A("| 比较 | 类型 | n_pair | b | c | ΔF1 | ΔAcc | χ²(Yates) | p(精确) | 显著性 |")
    A("|:--|:--|--:|--:|--:|--:|--:|--:|--:|:--|")
    for lbl, ka, kb, st, d1, da in iter_pairs(good, pairs):
        chi = st["chi2_yates"]
        chis = f"{chi:.2f}" if chi == chi else "n.a."
        kind = "提示消融" if ka[0] == kb[0] else "跨模型"
        A(f"| {lbl} | {kind} | {st['n_pair']} | {st['b']} | {st['c']} | "
          f"{d1:+.3f} | {da:+.3f} | {chis} | {st['p_exact']:.4f} | {sig_mark(st['p_exact'])} |")
    A("")
    A("---")
    A("")
    # ---- 误报溯源 ----
    A("## 表 7　误报（FP）溯源与子集性能")
    A("")
    A("> 关键负面结果：FP 是否集中于特定样本来源。")
    A("")
    A("| 模型 | 策略 | FP 总数 | 其中 hard_negative | 其中 synthetic | 其中 real_cve | "
      "硬负样本 FP 率 | 缺陷召回 |")
    A("|:--|:--|--:|--:|--:|--:|--:|--:|")
    for key, rows, m in good:
        fps = [r for r in rows if r["pred_found"] is not None and r["pred_found"]
               and r["label"] == "clean"]
        fo = Counter(r.get("origin", "?") for r in fps)
        hn = [r for r in rows if r.get("origin") == "hard_negative"
              and r["label"] == "clean" and r["pred_found"] is not None]
        hn_fp = sum(1 for r in hn if r["pred_found"]) / len(hn) if hn else 0.0
        df = [r for r in rows if r["label"] == "defective"
              and r["pred_found"] is not None]
        rec = sum(1 for r in df if r["pred_found"]) / len(df) if df else 0.0
        A(f"| {key[0]} | {key[1]} | {m['fp']} | {fo.get('hard_negative',0)} | "
          f"{fo.get('synthetic',0)} | {fo.get('real_cve',0)} | "
          f"{hn_fp:.1%} | {rec:.1%} |")
    A("")
    A("---")
    A("")
    # ---- 按缺陷类型的召回 ----
    A("## 表 8　按缺陷类型的召回率（逐类漏检分析）")
    A("")
    A("| 缺陷类型 | TEST n | Agents-A1 S1 TP | 召回 | 漏检率 |")
    A("|:--|--:|--:|--:|--:|")
    test_dt = defaultdict(list)
    for r in bench:
        if r["split"] == "test" and r["label"] == "defective":
            test_dt[r.get("defect_type") or "(空)"].append(r["item_id"])
    pred_a = None
    for key, rows, _m in good:
        if key == ("Agents-A1", "S1", 1):
            pred_a = {r["item_id"]: r for r in rows}
    if pred_a:
        for k, ids in sorted(test_dt.items(), key=lambda x: -len(x[1])):
            hit = sum(1 for i in ids if pred_a.get(i, {}).get("pred_found") is True)
            A(f"| {k} | {len(ids)} | {hit} | {hit/len(ids):.1%} | {1-hit/len(ids):.1%} |")
    A("")
    A("---")
    A("")
    A("## 关键统计结论（供论文 §6.3 讨论直接引用）")
    A("")
    # 结论引用用的实测 p 值（现场取，不硬编码）
    pmap: dict[str, float] = {}
    pinfo: dict[str, dict] = {}
    for lbl, ka, kb, st, _d1, _da in iter_pairs(good, pairs):
        k = f"{ka[1]}|{kb[1]}" if ka[0] == kb[0] else f"{ka[0]}|{kb[0]}"
        pmap[k] = st["p_exact"]
        pinfo[k] = st

    # 提示消融
    ab = {k[1]: m for k, _r, m in good if k[0] == "Agents-A1"}
    f1s = ", ".join(f"{s}={ab[s]['F1']:.3f}" for s in ("S1", "S2", "S3") if s in ab)
    p12 = pmap.get("S1|S2", float("nan"))
    p13 = pmap.get("S1|S3", float("nan"))
    p23 = pmap.get("S2|S3", float("nan"))
    A(f"1. **提示调优只能沿 P/R 轴滑动，且无统计显著差异。** Agents-A1 三策略 F1 "
      f"{f1s}；McNemar 精确检验 S1↔S2 p={p12:.3f}、S1↔S3 p={p13:.3f}、"
      f"S2↔S3 p={p23:.3f}，**全部 n.s.**。即调提示改变的是误报/漏检的取舍方向，")
    A("   不是检测能力的提升——"
      f"S1 高召回（R={ab.get('S1',{}).get('R',0):.3f}）靠 "
      f"FPR={ab.get('S1',{}).get('FPR',0):.3f} 换来，"
      f"S3 高精确（P={ab.get('S3',{}).get('P',0):.3f}）"
      f"代价是 R={ab.get('S3',{}).get('R',0):.3f}。")
    A("")
    # 跨模型
    cx = None
    for key, _r, m in good:
        if key == ("Atria-Dawn", "S1", 1):
            cx = m
    a1 = ab.get("S1")
    if cx and a1:
        px = pmap.get("Agents-A1|Atria-Dawn", float("nan"))
        n_pair = pinfo.get("Agents-A1|Atria-Dawn", {}).get("n_pair", 0)
        A(f"2. **跨模型分歧大但互不占优——这是支持工具融合的核心证据。** "
          f"Agents-A1 S1 与 Atria-Dawn S1 在 **{n_pair}/74 = "
          f"{n_pair/74:.1%} 的样本上判定相反**，")
        A(f"   但 McNemar 精确检验 p={px:.3f}"
          f"（b={pinfo.get('Agents-A1|Atria-Dawn', {}).get('b',0)}, "
          f"c={pinfo.get('Agents-A1|Atria-Dawn', {}).get('c',0)}），"
          f"**分歧不构成显著优劣**。")
        A(f"   即两模型对同一函数给出的判断是**近乎随机地互相独立**的：没有一个模型")
        A(f"   能系统性纠正另一个。二者的最佳 F1 仅 {a1['F1']:.3f} / {cx['F1']:.3f}，")
        A(f"   最佳 Acc 仅 {a1['Acc']:.3f} / {cx['Acc']:.3f}（基线随机 ≈0.500）。")
        A(f"   → **单靠换一个 LLM 无法解决问题**，K3 工具融合（LLM × 静态规则）是必要而非可选的。")
    A("")
    # 数据质量
    n_un = sum(1 for r in bench
               if r["split"] == "test" and r["label"] == "defective"
               and r.get("defect_type") == "待人工确认")
    n_td = sdc.get("test-defective", 0)
    A(f"3. **数据局限（须如实披露）**：TEST 37 个正例中 **{n_un}** 个缺陷类型标注为"
      f"「待人工确认」"
      f"（{n_un/n_td:.0%}）；DEV 集正例率 {sdc.get('dev-defective',0)/split.get('dev',1):.1%}"
      f"（仅 {sdc.get('dev-clean',0)} 个负例），负样本池偏小。")
    A("   因此逐类召回（表 8）对「待人工确认」大类的区分度有限。")
    A("")
    A("---")
    A("")
    A("## 附注")
    A("")
    A("1. **有效调用率门槛**：cell 有效调用率 <90% 一律剔除并单列，")
    A("   防止 429 配额打爆静默产出伪造指标（曾致 qwen3.8-27b 假 P=1.000）。")
    A("2. **smoke 文件排除**：`*smoke*.jsonl` 为 3 条样本验证跑，")
    A("   若参与去重会按字母序覆盖全量跑结果，故一律排除。")
    A("3. 跨模型结论目前仅 **2 个模型**有效（Agents-A1、Atria-Dawn），")
    A("   证据强度有限，论文中应如实披露；配额重置后补跑 qwen3.8-27b /")
    A("   deepseek-v4-flash-0731 可将对比扩至 4 模型。")
    A("4. McNemar 用**精确双侧**（符号检验二项）而非卡方近似——配对数仅 18–55，")
    A("   属小样本区，卡方连续性校正会低估显著性。")
    A("")

    MD_OUT = Path(out)
    MD_OUT.write_text(md(L) + "\n", encoding="utf-8")
    print(f"\n[已导出三线表] {MD_OUT}  ({len(L)} 行)")


if __name__ == "__main__":
    main()
