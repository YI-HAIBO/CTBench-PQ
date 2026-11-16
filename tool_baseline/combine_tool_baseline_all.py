#!/usr/bin/env python3
"""M2 扩展：把工具校准从 9 项（binsec+dudect）扩到 24 microbench + 3 kyber（>=27 项）。

数据来源：
  - binsec verdict : mb2_results_final.jsonl（24 项，本机已有）+ BINSEC_KYBER（3 项）
  - dudect verdict : dudect_fixtures/dudect_results_final.jsonl（9 项已有）
                     + dudect_fixtures_all/dudect_all_results.txt（24 项 _all，VM 批量跑测）
  - source GT      : microbench/manifest.json（defective/clean）+ kyber GT
  - platform GT    : 由 dudect 实测驱动（LEAK->defective 真泄漏；CT->clean gcc/硬件缓解）

组合规则（沿用 combine_tool_baseline.py）：
  任一工具自信 LEAK -> LEAK；否则 (binsec CT 或 timeout) 且 dudect CT -> CT；否则 UNKNOWN。

输出：R_t/P_t（TP/FP/FN/TN）双口径 + Clopper-Pearson 95% CI（复用 _m1_m2 的二分）。
"""
import json, re, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB_RESULTS = HERE / "mb2_results_final.jsonl"
DUDECT_OLD = HERE / "dudect_fixtures" / "dudect_results_final.jsonl"
DUDECT_ALL = HERE / "dudect_fixtures_all" / "dudect_all_final.txt"
MANIFEST = HERE / "microbench" / "manifest.json"

# binsec kyber（来自 tool_baseline_report.md §3 实测；timeout=探索不完->保守 insecure）
BINSEC_KYBER = {
    "KY-VERIFY-CT": {"status": "secure", "timeout": False},
    "KY-CLEAN-8": {"status": "insecure", "timeout": True},
    "KY-DEFECT-8": {"status": "insecure", "timeout": True},
}
# kyber source GT（defective=含 div 的缺陷模式；clean=CT 实现）
KY_GT = {
    "KY-VERIFY-CT": ("clean", "clean", "Kyber verify/cmov CT 实现"),
    "KY-CLEAN-8": ("clean", "clean", "poly_compress 修复后 CT（binsec timeout-FP 被 dudect 覆盖）"),
    "KY-DEFECT-8": ("defective", "clean", "poly_compress 修复前 /KYBER_Q（gcc15.2 魔数乘法缓解）"),
}


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").strip().splitlines() if l.strip()]


def load_dudect_all(p: Path):
    """解析 VM 批处理输出 'RESULT <name> rc=<n> sec=<s>' -> {item_id: (rc, sec)}"""
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"RESULT (\w+) rc=(\d+) sec=(\d+)", line.strip())
        if m:
            name = m.group(1)                 # e.g. dudect_mb_d01_all
            iid = "MB-" + name[len("dudect_mb_"):].split("_all")[0].upper()
            out[iid] = (int(m.group(2)), int(m.group(3)))
    return out


def clopper_pearson_lower(k, n, alpha=0.05):
    """单侧下界（P(X>=k) >= alpha/2），与 _m1_m2.py 同口径。"""
    if k == 0:
        return 0.0
    if n == 0:
        return 0.0
    if k >= n:
        return (alpha / 2) ** (1.0 / n)
    # 二分找 p 使 P(X>=k | n,p) = alpha/2
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        p = 0.0
        for x in range(k, n + 1):
            p += math.comb(n, x) * (mid ** x) * ((1 - mid) ** (n - x))
        if p < alpha / 2:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    binsec_mb = {r["item_id"]: r for r in load_jsonl(MB_RESULTS)}
    dudect_old = {r["item_id"]: r for r in load_jsonl(DUDECT_OLD)}
    dudect_all = load_dudect_all(DUDECT_ALL)

    rows = []
    # --- microbench 24 项（source GT 来自 manifest）---
    for it in manifest["items"]:
        iid = it["item_id"]
        b = binsec_mb.get(iid)
        b_status = b["status"] if b else "unknown"
        b_timeout = False
        # dudect verdict：优先 _all 实测，回退旧 9 项
        d_verdict = None
        if iid in dudect_all:
            rc, sec = dudect_all[iid]
            d_verdict = "LEAK" if rc == 0 else ("CT" if rc == 124 else None)
        elif iid in dudect_old:
            d_verdict = dudect_old[iid].get("verdict")
        src_gt = it["label"]
        # platform GT 由 dudect 实测驱动（仅 D* defective 项；dudect 未测则沿用 source）
        plat_gt = src_gt
        if d_verdict == "LEAK":
            plat_gt = "defective"
        elif d_verdict == "CT" and src_gt == "defective":
            plat_gt = "clean"   # gcc/硬件缓解，本平台无实际泄漏
        rows.append((iid, b_status, b_timeout, d_verdict, src_gt, plat_gt, it["pattern"]))
    # --- kyber 3 项 ---
    for iid, (src_gt, plat_gt, note) in KY_GT.items():
        b = BINSEC_KYBER[iid]
        d_verdict = dudect_old.get(iid, {}).get("verdict")
        rows.append((iid, b["status"], b["timeout"], d_verdict, src_gt, plat_gt, note))

    # --- 组合 + 指标 ---
    def combine(b_status, b_timeout, d_verdict):
        b_leak = (b_status == "insecure" and not b_timeout)
        b_ct = (b_status == "secure" and not b_timeout)
        if b_leak or d_verdict == "LEAK":
            return "LEAK"
        if (b_ct or b_timeout) and d_verdict == "CT":
            return "CT"
        if b_leak:
            return "LEAK"
        if b_ct and d_verdict is None:
            return "CT"   # binsec 自信 CT 且 dudect 未测 -> 单工具 CT
        return "UNKNOWN"

    def verdict(comb, gt):
        if comb == "LEAK":
            return "TP" if gt == "defective" else "FP"
        if comb == "CT":
            return "TN" if gt == "clean" else "FN"
        return "unknown"

    def metrics(rows, gt_key):
        tp = fn = fp = tn = 0
        for iid, bs, bt, dv, sgt, pgt, pat in rows:
            comb = combine(bs, bt, dv)
            v = verdict(comb, pgt if gt_key == "plat" else sgt)
            if v == "TP": tp += 1
            elif v == "FN": fn += 1
            elif v == "FP": fp += 1
            elif v == "TN": tn += 1
        n = tp + fn + fp + tn
        P = tp / (tp + fp) if (tp + fp) else 1.0
        R = tp / (tp + fn) if (tp + fn) else 0.0
        return tp, fn, fp, tn, P, R

    print("=" * 92)
    print(f"M2 工具校准扩展（microbench 24 + kyber 3 = {len(rows)} 项）")
    print("=" * 92)
    print(f"{'item':12}{'binsec':16}{'dudect':9}{'comb':8}{'src_gt':10}{'plat_gt':10}  pattern")
    for iid, bs, bt, dv, sgt, pgt, pat in rows:
        comb = combine(bs, bt, dv)
        bs_s = bs + ("(to)" if bt else "")
        print(f"{iid:12}{bs_s:16}{str(dv):9}{comb:8}{sgt:10}{pgt:10}  {pat}")

    for label, gt_key in (("source", "src"), ("platform", "plat")):
        tp, fn, fp, tn, P, R = metrics(rows, gt_key)
        n = tp + fn + fp + tn
        F1 = 2 * P * R / (P + R) if (P + R) else 0.0
        # R_t/P_t Clopper-Pearson 单侧下界
        R_lo = clopper_pearson_lower(tp, tp + fn) if (tp + fn) else 0.0
        P_lo = clopper_pearson_lower(tp, tp + fp) if (tp + fp) else 1.0
        print(f"\n[{label} 级 GT] n={n} TP={tp} FN={fn} FP={fp} TN={tn} "
              f"P={P*100:.1f}% R={R*100:.1f}% F1={F1:.3f}")
        print(f"   R_t 下界 CI = {R_lo:.3f}  (R_t={R:.3f})")
        print(f"   P_t 下界 CI = {P_lo:.3f}  (P_t={P:.3f})")
    print()


if __name__ == "__main__":
    main()
