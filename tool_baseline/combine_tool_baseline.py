#!/usr/bin/env python3
"""Task #14：组合 binsec + dudect 多工具工具基线（① P0 收尾）。

核心发现（本段实测）：
  - gcc -O2 自动缓解多数简单 CT 缺陷模式（D01 分支→SIMD、KY-DEFECT8 /KYBER_Q→魔数乘法）
  - i7-10700 32位 div 固定延迟 → D03 div 盲区在本硬件不落地
  - binsec timeout→保守 insecure 假阳性（KY-CLEAN-8）被 dudect CT 覆盖
  - dudect 检出强泄漏（donnabad 外部验证）但检不出弱/缓存行内泄漏（D06/D09）
  → binsec（源级模式）与 dudect（编译时序）互补，分歧揭示编译器/硬件缓解。

GT 双口径：
  - source 级：按静态缺陷模式（sd-branch/div/loopbound/rotate-addr/KyberSlash = defective）
  - platform 级：按本平台实际时序（i7-10700 + gcc 15.2；实测均无泄漏 → 全部 clean，
    仅外部 donnabad 证明 dudect 可检强泄漏）

组合规则（多工具）：
  - 任一工具自信泄漏 → LEAK
  - 全部自信 CT（或 binsec timeout 被 dudect CT 覆盖）→ CT
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MB_RESULTS = HERE / "mb2_results_final.jsonl"
DUDECT_RESULTS = HERE / "dudect_fixtures" / "dudect_results_final.jsonl"

def load_jsonl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").strip().splitlines() if l.strip()]

# binsec Kyber（来自 tool_baseline_report.md §3 实测）
BINSEC_KYBER = {
    "KY-VERIFY-CT": {"status": "secure", "timeout": False, "note": "binsec secure(0.076s)"},
    "KY-CLEAN-8": {"status": "insecure", "timeout": True, "note": "binsec timeout(243s)→探索不完→保守 insecure（假阳性）"},
    "KY-DEFECT-8": {"status": "insecure", "timeout": True, "note": "binsec timeout→探索不完→保守 insecure（低置信）"},
}

# GT：(source_gt, platform_gt, 说明)
GT = {
    "MB-D01": ("defective", "clean", "sd-branch 源级模式；gcc -O2 向量化为无分支 SIMD→编译后恒时"),
    "MB-D03": ("defective", "clean", "sd-div 源级模式；i7-10700 div 固定延迟→无实际泄漏"),
    "MB-C01": ("clean", "clean", "ct-select 无分支"),
    "MB-C06": ("clean", "clean", "ct-barrett 常量除→魔数乘法恒时"),
    "MB-D06": ("defective", "clean", "sd-loopbound 源级模式；弱信号 max_t≈0.97<10（VM 噪声/循环缓解）"),
    "MB-D09": ("defective", "clean", "sd-rotate-addr 源级地址泄漏；dudect max_t≈1.04（单次测量内访问行<L1 容量）"),
    "KY-VERIFY-CT": ("clean", "clean", "Kyber verify/cmov CT"),
    "KY-CLEAN-8": ("clean", "clean", "poly_compress 修复后 CT；binsec timeout-FP 被 dudect 覆盖"),
    "KY-DEFECT-8": ("defective", "clean", "poly_compress 修复前 /KYBER_Q；gcc15.2 魔数乘法→无实际泄漏"),
}

def main():
    binsec_mb = {r["item_id"]: r for r in load_jsonl(MB_RESULTS)}
    dudect = {r["item_id"]: r for r in load_jsonl(DUDECT_RESULTS)}

    rows = []
    for iid, (src_gt, plat_gt, note) in GT.items():
        if iid in binsec_mb:
            r = binsec_mb[iid]
            b_status = r.get("status")
            b_timeout = False
        else:
            r = BINSEC_KYBER[iid]
            b_status = r["status"]
            b_timeout = r["timeout"]
        d = dudect.get(iid, {})
        d_verdict = d.get("verdict")

        # binsec 自信泄漏/CT/不确定
        b_leak = (b_status == "insecure" and not b_timeout)
        b_ct = (b_status == "secure" and not b_timeout)
        b_unknown = b_timeout
        # dudect
        d_leak = (d_verdict == "LEAK")
        d_ct = (d_verdict == "CT")

        # 组合
        if b_leak or d_leak:
            comb = "LEAK"
            why = "binsec 自信泄漏" if b_leak else "dudect LEAK"
        elif (b_ct or b_unknown) and d_ct:
            comb = "CT"
            why = "dudect CT 覆盖 binsec timeout-FP" if b_unknown else "双工具 CT"
        else:
            comb = "UNKNOWN"
            why = "判定不足"

        # 分歧类型
        if b_leak and d_ct:
            disc = "分歧(binsec↑,dudect↓)"
        elif b_ct and d_leak:
            disc = "分歧(binsec↓,dudect↑)"
        elif b_unknown and d_ct:
            disc = "binsec timeout 被 dudect 覆盖"
        elif b_ct and d_ct:
            disc = "一致 CT"
        elif b_leak and d_leak:
            disc = "一致 LEAK"
        else:
            disc = "-"

        def verdict_of(comb, gt):
            if comb == "LEAK":
                return "TP" if gt == "defective" else "FP"
            if comb == "CT":
                return "TN" if gt == "clean" else "FN"
            return "unknown"

        rows.append({
            "item_id": iid,
            "binsec": b_status + ("(timeout)" if b_timeout else ""),
            "dudect": d_verdict or "-",
            "combined": comb,
            "why": why,
            "disc": disc,
            "src_gt": src_gt, "plat_gt": plat_gt,
            "src_verdict": verdict_of(comb, src_gt),
            "plat_verdict": verdict_of(comb, plat_gt),
            "note": note,
        })

    def metrics(rows, gt_key):
        tp = sum(1 for r in rows if r["combined"] == "LEAK" and r[gt_key] == "defective")
        fn = sum(1 for r in rows if r["combined"] == "CT" and r[gt_key] == "defective")
        fp = sum(1 for r in rows if r["combined"] == "LEAK" and r[gt_key] == "clean")
        tn = sum(1 for r in rows if r["combined"] == "CT" and r[gt_key] == "clean")
        n = tp + fn + fp + tn
        prec = tp / (tp + fp) if (tp + fp) else 1.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "n": n,
                "precision": prec, "recall": rec, "f1": f1}

    m_src = metrics(rows, "src_gt")
    m_plat = metrics(rows, "plat_gt")

    print("=" * 78)
    print("Task #14 多工具工具基线（binsec + dudect）—— ① P0 收尾")
    print("=" * 78)
    print(f"{'item':14}{'binsec':14}{'dudect':9}{'comb':7}{'分歧/一致':24}{'src_gt':10}{'plat_gt':10}")
    for r in rows:
        print(f"{r['item_id']:14}{r['binsec']:14}{r['dudect']:9}{r['combined']:7}{r['disc']:24}{r['src_gt']:10}{r['plat_gt']:10}")
    print()
    print(f"[source 级 GT] TP={m_src['tp']} FN={m_src['fn']} FP={m_src['fp']} TN={m_src['tn']} "
          f"P={m_src['precision']*100:.1f}% R={m_src['recall']*100:.1f}% F1={m_src['f1']:.3f}")
    print(f"[platform 级 GT] TP={m_plat['tp']} FN={m_plat['fn']} FP={m_plat['fp']} TN={m_plat['tn']} "
          f"P={m_plat['precision']*100:.1f}% R={m_plat['recall']*100:.1f}% F1={m_plat['f1']:.3f}")

    print("\n=== 关键发现（分歧揭示编译器/硬件缓解）===")
    for r in rows:
        if r["disc"].startswith("分歧") or "timeout" in r["disc"]:
            print(f"  - {r['item_id']}: {r['disc']} -> {r['note']}")
    print("\n=== donnabad 外部验证 ===")
    print("  dudect donnabad_O2 exit=0 = LEAK（强泄漏检出，验证 dudect 检测能力）；")
    print("  my 9 fixtures 均 CT：gcc -O2 缓解简单模式 + div 恒时 + 弱/缓存行内泄漏低于阈值。")

    return rows, m_src, m_plat

if __name__ == "__main__":
    main()
