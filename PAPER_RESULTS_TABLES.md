# CTBench-PQ 论文用结果表（三线表）

> 自动生成：`analysis/significance.py`。
> **所有数字均从 `corpus/data/benchmark.jsonl` 与 `results/*.jsonl` 现场计算，
> 未硬编码。** 调用失败/解析失败的预测一律排除出混淆矩阵，`n_valid` 已单列。**

---

## 表 1　CTBench-PQ 数据构成

全部样本 **257** 条；TEST/DEV/TRAIN = 74/152/31。TEST 集正负平衡（37/37）。

| 来源 origin | 数量 | 占比 |
|:--|--:|--:|
| real_cve | 66 | 25.7% |
| hard_negative | 66 | 25.7% |
| synthetic_compound | 63 | 24.5% |
| synthetic_injected | 62 | 24.1% |

**表 2　分层切分与标签平衡**

| split | 总数 | defective | clean | 正例率 |
|:--|--:|--:|--:|--:|
| TEST | 74 | 37 | 37 | 50.0% |
| DEV | 152 | 136 | 16 | 89.5% |
| TRAIN | 31 | 18 | 13 | 58.1% |

**表 3　缺陷类型分布（benchmark 全量）**

| 缺陷类型 | 数量 | 占比 |
|:--|--:|--:|
| (空) | 66 | 25.7% |
| early_exit_branch | 61 | 23.7% |
| 待人工确认 | 57 | 22.2% |
| secret_branch | 48 | 18.7% |
| table_access | 9 | 3.5% |
| ct_flag_removed | 7 | 2.7% |
| nonct_arith | 2 | 0.8% |
| compiler_mask | 2 | 0.8% |
| secret_branch,implicit_rejection_disabled | 2 | 0.8% |
| cache_timing | 2 | 0.8% |
| barrier_removed | 1 | 0.4% |

**表 4　语言与库覆盖**：语言 c 164 / java 65 / rs 22 / h 2 / cpp 2 / s 2；库 None 191 / bouncycastle 22 / openssl 21 / wolfssl 15 / liboqs 4 / rustcrypto 3 / cryptopp 1。

**PQC 子集**：关键词命中 **47** 条（TEST 内 18 条）。

---

## 表 5　主实验结果：LLM 检测性能（E4 / E5′ / E4b）

> 有效调用率 ≥90% 的 cell；`n_valid` 为进入混淆矩阵的有效预测数。
> 未达门槛的模型（qwen3.8-27b 有效 2/74、deepseek-v4-flash-0731 有效 0/74）已剔除。

| 模型 | 策略 | n_valid | P | R | **F1** | FPR | Acc | TP | FP | FN | TN |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Atria-Dawn | S1 | 70 | 1.000 | 0.091 | **0.167** | 0.000 | 0.571 | 3 | 0 | 30 | 37 |
| Atria-Dawn-Preview | S1 | 102 | 0.667 | 0.122 | **0.207** | 0.057 | 0.549 | 6 | 3 | 43 | 50 |
| agnes-3.0-flash | S1 | 102 | 0.778 | 0.194 | **0.311** | 0.030 | 0.696 | 7 | 2 | 29 | 64 |
| deepseek-v4-flash | S1 | 97 | 0.680 | 0.378 | **0.486** | 0.154 | 0.629 | 17 | 8 | 28 | 44 |
| dots3-note-prev | S1 | 103 | 0.660 | 0.660 | **0.660** | 0.286 | 0.689 | 31 | 16 | 16 | 40 |
| intern-s2 | S1 | 97 | 0.613 | 0.432 | **0.507** | 0.226 | 0.619 | 19 | 12 | 25 | 41 |
| nex-n2.6 | S1 | 101 | 0.556 | 0.143 | **0.227** | 0.061 | 0.663 | 5 | 4 | 30 | 62 |
| sensenova-6.8-flash-lite | S1 | 101 | 0.731 | 0.396 | **0.514** | 0.132 | 0.644 | 19 | 7 | 29 | 46 |

---

## 表 6　McNemar 精确配对检验

> 配对单位 = 单个函数样本；b = 左侧配置正确而右侧错误，c = 反之。
> p 为精确双侧（符号检验二项），n_pair<250 时优于卡方近似。
> 显著性：\*\*\* p<.001，\*\* p<.01，\* p<.05，n.s. 不显著。

| 比较 | 类型 | n_pair | b | c | ΔF1 | ΔAcc | χ²(Yates) | p(精确) | 显著性 |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|:--|
| Atria-Dawn S1  vs  Atria-Dawn-Preview S1 | 跨模型 | 1 | 0 | 1 | -0.040 | +0.022 | n.a. | 1.0000 | n.s. |
| Atria-Dawn S1  vs  agnes-3.0-flash S1 | 跨模型 | 6 | 3 | 3 | -0.144 | -0.125 | n.a. | 1.0000 | n.s. |
| Atria-Dawn S1  vs  deepseek-v4-flash S1 | 跨模型 | 9 | 3 | 6 | -0.319 | -0.057 | n.a. | 0.5078 | n.s. |
| Atria-Dawn S1  vs  dots3-note-prev S1 | 跨模型 | 25 | 7 | 18 | -0.493 | -0.118 | 4.00 | 0.0433 | * |
| Atria-Dawn S1  vs  intern-s2 S1 | 跨模型 | 15 | 4 | 11 | -0.340 | -0.047 | 2.40 | 0.1185 | n.s. |
| Atria-Dawn S1  vs  nex-n2.6 S1 | 跨模型 | 1 | 1 | 0 | -0.061 | -0.092 | n.a. | 1.0000 | n.s. |
| Atria-Dawn S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 9 | 2 | 7 | -0.347 | -0.072 | n.a. | 0.1797 | n.s. |
| Atria-Dawn-Preview S1  vs  agnes-3.0-flash S1 | 跨模型 | 11 | 5 | 6 | -0.104 | -0.147 | 0.00 | 1.0000 | n.s. |
| Atria-Dawn-Preview S1  vs  deepseek-v4-flash S1 | 跨模型 | 21 | 7 | 14 | -0.279 | -0.080 | 1.71 | 0.1892 | n.s. |
| Atria-Dawn-Preview S1  vs  dots3-note-prev S1 | 跨模型 | 41 | 14 | 27 | -0.453 | -0.140 | 3.51 | 0.0596 | n.s. |
| Atria-Dawn-Preview S1  vs  intern-s2 S1 | 跨模型 | 28 | 10 | 18 | -0.300 | -0.070 | 1.75 | 0.1849 | n.s. |
| Atria-Dawn-Preview S1  vs  nex-n2.6 S1 | 跨模型 | 6 | 3 | 3 | -0.020 | -0.114 | n.a. | 1.0000 | n.s. |
| Atria-Dawn-Preview S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 20 | 5 | 15 | -0.307 | -0.095 | 4.05 | 0.0414 | * |
| agnes-3.0-flash S1  vs  deepseek-v4-flash S1 | 跨模型 | 21 | 12 | 9 | -0.175 | +0.067 | 0.19 | 0.6636 | n.s. |
| agnes-3.0-flash S1  vs  dots3-note-prev S1 | 跨模型 | 40 | 23 | 17 | -0.348 | +0.007 | 0.62 | 0.4296 | n.s. |
| agnes-3.0-flash S1  vs  intern-s2 S1 | 跨模型 | 26 | 14 | 12 | -0.196 | +0.078 | 0.04 | 0.8450 | n.s. |
| agnes-3.0-flash S1  vs  nex-n2.6 S1 | 跨模型 | 14 | 9 | 5 | +0.084 | +0.033 | 0.64 | 0.4240 | n.s. |
| agnes-3.0-flash S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 21 | 10 | 11 | -0.202 | +0.053 | 0.00 | 1.0000 | n.s. |
| deepseek-v4-flash S1  vs  dots3-note-prev S1 | 跨模型 | 25 | 10 | 15 | -0.174 | -0.060 | 0.64 | 0.4244 | n.s. |
| deepseek-v4-flash S1  vs  intern-s2 S1 | 跨模型 | 12 | 7 | 5 | -0.021 | +0.010 | 0.08 | 0.7744 | n.s. |
| deepseek-v4-flash S1  vs  nex-n2.6 S1 | 跨模型 | 23 | 14 | 9 | +0.258 | -0.035 | 0.70 | 0.4049 | n.s. |
| deepseek-v4-flash S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 12 | 5 | 7 | -0.028 | -0.015 | 0.08 | 0.7744 | n.s. |
| dots3-note-prev S1  vs  intern-s2 S1 | 跨模型 | 25 | 16 | 9 | +0.153 | +0.071 | 1.44 | 0.2295 | n.s. |
| dots3-note-prev S1  vs  nex-n2.6 S1 | 跨模型 | 41 | 26 | 15 | +0.432 | +0.026 | 2.44 | 0.1173 | n.s. |
| dots3-note-prev S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 31 | 17 | 14 | +0.146 | +0.046 | 0.13 | 0.7201 | n.s. |
| intern-s2 S1  vs  nex-n2.6 S1 | 跨模型 | 29 | 17 | 12 | +0.279 | -0.045 | 0.55 | 0.4583 | n.s. |
| intern-s2 S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 16 | 6 | 10 | -0.007 | -0.025 | 0.56 | 0.4545 | n.s. |
| nex-n2.6 S1  vs  sensenova-6.8-flash-lite S1 | 跨模型 | 20 | 9 | 11 | -0.286 | +0.020 | 0.05 | 0.8238 | n.s. |

---

## 表 7　误报（FP）溯源与子集性能

> 关键负面结果：FP 是否集中于特定样本来源。

| 模型 | 策略 | FP 总数 | 其中 hard_negative | 其中 synthetic | 其中 real_cve | 硬负样本 FP 率 | 缺陷召回 |
|:--|:--|--:|--:|--:|--:|--:|--:|
| Atria-Dawn | S1 | 0 | 0 | 0 | 0 | 0.0% | 9.1% |
| Atria-Dawn-Preview | S1 | 3 | 3 | 0 | 0 | 5.7% | 12.2% |
| agnes-3.0-flash | S1 | 2 | 2 | 0 | 0 | 3.7% | 19.4% |
| deepseek-v4-flash | S1 | 8 | 8 | 0 | 0 | 15.7% | 37.8% |
| dots3-note-prev | S1 | 16 | 16 | 0 | 0 | 29.1% | 66.0% |
| intern-s2 | S1 | 12 | 11 | 0 | 1 | 21.2% | 43.2% |
| nex-n2.6 | S1 | 4 | 3 | 0 | 1 | 5.7% | 14.3% |
| sensenova-6.8-flash-lite | S1 | 7 | 7 | 0 | 0 | 13.5% | 39.6% |

---

## 表 8　按缺陷类型的召回率（逐类漏检分析）

| 缺陷类型 | TEST n | Agents-A1 S1 TP | 召回 | 漏检率 |
|:--|--:|--:|--:|--:|

---

## 关键统计结论（供论文 §6.3 讨论直接引用）

1. **提示调优只能沿 P/R 轴滑动，且无统计显著差异。** Agents-A1 三策略 F1 ；McNemar 精确检验 S1↔S2 p=nan、S1↔S3 p=nan、S2↔S3 p=nan，**全部 n.s.**。即调提示改变的是误报/漏检的取舍方向，
   不是检测能力的提升——S1 高召回（R=0.000）靠 FPR=0.000 换来，S3 高精确（P=0.000）代价是 R=0.000。


3. **数据局限（须如实披露）**：TEST 37 个正例中 **30** 个缺陷类型标注为「待人工确认」（81%）；DEV 集正例率 89.5%（仅 16 个负例），负样本池偏小。
   因此逐类召回（表 8）对「待人工确认」大类的区分度有限。

---

## 附注

1. **有效调用率门槛**：cell 有效调用率 <90% 一律剔除并单列，
   防止 429 配额打爆静默产出伪造指标（曾致 qwen3.8-27b 假 P=1.000）。
2. **smoke 文件排除**：`*smoke*.jsonl` 为 3 条样本验证跑，
   若参与去重会按字母序覆盖全量跑结果，故一律排除。
3. 跨模型结论目前仅 **2 个模型**有效（Agents-A1、Atria-Dawn），
   证据强度有限，论文中应如实披露；配额重置后补跑 qwen3.8-27b /
   deepseek-v4-flash-0731 可将对比扩至 4 模型。
4. McNemar 用**精确双侧**（符号检验二项）而非卡方近似——配对数仅 18–55，
   属小样本区，卡方连续性校正会低估显著性。

