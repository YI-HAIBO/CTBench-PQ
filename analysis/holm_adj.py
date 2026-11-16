# -*- coding: utf-8 -*-
# Holm-Bonferroni 校正：36 对 McNemar（extended 92 非噪声，9 检测器：D1,D2,D3,deepseek,intern,sensenova,dots3,agnes,nex）
# 数据源：analysis/recompute_extended.py 输出（agnes 最终合并态，91/92 有效）
pairs = [
    ("D1 vs D2", 32, 3, 0.0000),
    ("D1 vs D3", 34, 4, 0.0000),
    ("D1 vs deepseek", 16, 1, 0.0003),
    ("D1 vs intern", 15, 3, 0.0075),
    ("D1 vs sensenova", 20, 0, 0.0000),
    ("D1 vs dots3", 14, 11, 0.6900),
    ("D1 vs agnes", 33, 2, 0.0000),
    ("D1 vs nex", 32, 1, 0.0000),
    ("D2 vs D3", 11, 11, 1.0000),
    ("D2 vs deepseek", 4, 13, 0.0490),
    ("D2 vs intern", 4, 22, 0.0005),
    ("D2 vs sensenova", 4, 14, 0.0309),
    ("D2 vs dots3", 2, 29, 0.0000),
    ("D2 vs agnes", 7, 6, 1.0000),
    ("D2 vs nex", 6, 3, 0.5078),
    ("D3 vs deepseek", 4, 14, 0.0309),
    ("D3 vs intern", 6, 23, 0.0023),
    ("D3 vs sensenova", 6, 18, 0.0227),
    ("D3 vs dots3", 5, 33, 0.0000),
    ("D3 vs agnes", 10, 8, 0.8145),
    ("D3 vs nex", 9, 8, 1.0000),
    ("deepseek vs intern", 3, 8, 0.2266),
    ("deepseek vs sensenova", 5, 4, 1.0000),
    ("deepseek vs dots3", 2, 18, 0.0004),
    ("deepseek vs agnes", 14, 3, 0.0127),
    ("deepseek vs nex", 15, 4, 0.0192),
    ("intern vs sensenova", 10, 3, 0.0923),
    ("intern vs dots3", 5, 15, 0.0414),
    ("intern vs agnes", 21, 3, 0.0003),
    ("intern vs nex", 22, 3, 0.0002),
    ("sensenova vs dots3", 4, 21, 0.0009),
    ("sensenova vs agnes", 15, 3, 0.0075),
    ("sensenova vs nex", 15, 2, 0.0023),
    ("dots3 vs agnes", 31, 1, 0.0000),
    ("dots3 vs nex", 32, 2, 0.0000),
    ("agnes vs nex", 7, 6, 1.0000),
]
m = len(pairs)
ordered = sorted(pairs, key=lambda x: x[3])
adj = {}
prev = 0.0
for idx, (name, b, c, p) in enumerate(ordered):
    val = (m - idx) * p
    val = max(val, prev)
    val = min(1.0, val)
    prev = val
    adj[name] = val
print("Holm-Bonferroni (m=%d pairs)" % m)
print("%-26s %3s %3s %9s %9s %10s" % ("pair", "b", "c", "p_raw", "p_holm", "sig0.05"))
print("-" * 68)
for name, b, c, p in sorted(pairs, key=lambda x: x[3]):
    ph = adj[name]
    print("%-26s %3d %3d %9.4f %9.4f %10s" % (name, b, c, p, ph, "yes" if ph < 0.05 else "no"))
print()
print("=== key pair verdicts ===")
for k in ["D1 vs D2", "D1 vs D3", "D1 vs dots3", "D1 vs deepseek", "D1 vs intern", "D1 vs sensenova",
          "D1 vs nex", "D1 vs agnes",
          "D3 vs intern", "D3 vs sensenova", "D3 vs dots3", "D2 vs D3",
          "dots3 vs nex", "dots3 vs agnes",
          "deepseek vs intern", "intern vs sensenova", "deepseek vs sensenova",
          "D2 vs deepseek", "D2 vs intern", "D2 vs sensenova", "intern vs dots3"]:
    ph = adj[k]
    print("  %-26s p_holm=%.4f %s" % (k, ph, "SIG" if ph < 0.05 else "ns"))
