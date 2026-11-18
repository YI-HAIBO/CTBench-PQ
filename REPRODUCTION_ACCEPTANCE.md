# CTBench-PQ 第三方复现验收指南

> 本指南面向**外部独立团队/个人**：拿到本仓库（公开：`https://github.com/YI-HAIBO/CTBench-PQ`）
> 后，按以下步骤即可独立复现论文的 6 个核心结果锚点并回报验收结果。
>
> 目的：把 L4「真第三方人类团队复现」从"待外部协作"转化为**可执行的验收标准 + 回报模板**。
> 现有自动化复现已通过：离线自复现、VM 双环境（Ubuntu 26.04.1 / Python 3.14.4 与
> Windows / Python 3.13）、GitHub Actions 公开 runner 双平台矩阵三连通过
> （run #44230159660 / #44233550798 / #44241622940，2-OS ubuntu+macos）。

## 1. 环境要求

| 项 | 要求 |
|---|---|
| OS | Linux / macOS（推荐）；Windows 需 Git Bash + `python3` 别名（见 §6 平台限制） |
| Python | ≥ 3.10（CI 用 3.13；VM 验证 3.14.4 亦可） |
| 依赖 | 仅标准库 + `pypdf`（用于 PDF 校验，非必需） |
| 网络 | 无（reproduce.sh 全离线，不调用任何外部 API） |
| 时长 | 单次完整复现 ≤ 5 分钟（CI 实测 9–16s） |

## 2. 一键复现

```bash
git clone https://github.com/YI-HAIBO/CTBench-PQ.git
cd CTBench-PQ
bash reproduce.sh          # 5 步流水线，全离线
echo "exit=$?"             # 期望 exit=0
```

`reproduce.sh` 依次执行：

1. `analysis/significance.py` —— 主结果统计（McNemar 等）
2. `analysis/verify_merged_ceiling.py` —— merged 天花板/上界核验
3. `analysis/recompute_extended.py` —— extended 92 非噪声口径
4. `analysis/fdc_mi_measured_fusion.py` —— 实测融合（Binsec+dudect，AND-gating F1）
5. `analysis/verify_anchors.py` —— **6 个核心结果锚点自证**（任一 miss 返回非零）

## 3. 验收标准（6 锚点，全部必须命中）

`analysis/verify_anchors.py` 对以下 6 项逐值断言，**任一未命中即返回非零**：

1. **D1 merged Meas**：P=0.679 / R=0.633 / F1=0.655
2. **extended D1 非噪声 92**：P=0.488 / R=0.625 / F1=0.548
3. **D3 orig hunk-level**：F1=0.250
4. **§5.2 D3 merged**：F1=0.603
5. **9-item 工具融合锚点**：Binsec+dudect，R_t=0.9 / P_t=1.0，AND-gating F1=0.827
6. **M2 27-item source 校准**：R_t=0.846 / P_t=1.0；Clopper–Pearson 下界 R_t≥0.546 / P_t≥0.715

**验收通过** ⇔ `bash reproduce.sh` 全 5 步 RC=0 **且** `verify_anchors.py` 6/6 锚点命中
（等价于 job exit=0）。

## 4. 回报模板（第三方填写）

```markdown
# CTBench-PQ 复现回报
- 复现者（团队/个人）：________
- 日期：____
- 平台：____（OS / 架构）
- Python 版本：____
- `bash reproduce.sh` 退出码：____（期望 0）
- `verify_anchors.py` 锚点命中：____/6（期望 6/6）
- 总耗时：____
- 与 §3 表逐值偏差（若有，逐项列出）：____
- 结论：通过 / 未通过（注明失败步骤与原因）
```

## 5. 结果核验

- 若全通过：请回报 §4 表格；本仓库维护者将把该次复现记录写入 RELEASE_README.md
  （run 编号、平台、日期、锚点命中数）。
- 若未通过：请附 `reproduce.sh` 的完整 stdout/stderr 与失败步骤，维护者按
  `analysis/verify_anchors.py` 逐锚点定位。

## 6. 已知平台限制（windows-latest）

首次 3-OS CI 尝试（commit `cbbd0c5`，run #44240772791）中 `windows-latest` 在
`bash reproduce.sh` 步骤失败，推断为 Windows runner 的 Git Bash / `python3` 路径限制。
**建议**：Windows 下使用 Git Bash，并确保 `python3` 在 PATH（可 `alias python3=python`），
或直接使用 WSL / Linux / macOS。当前 CI 矩阵为 2-OS（`ubuntu-latest` + `macos-latest`），
双平台均通过；Windows 复现列为 follow-up。
