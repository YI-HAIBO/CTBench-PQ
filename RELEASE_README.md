# CTBench-PQ Release Package

**Repository** (public, finalized): `https://github.com/CTBench-PQ/CTBench-PQ`
**Release tag**: `v1.0`
**Corresponding author**: haiboyi@szpu.edu.cn
**Last evaluated**: 2026-11-12
**License**: research use; benchmark data under CC-BY-4.0, code under MIT

---

## What this package is

CTBench-PQ is the first benchmark and empirical capability profile for **constant-time
side-channel detection in post-quantum cryptographic code**. It evaluates how well
LLM-based detectors and a rule baseline detect constant-time violations, and shows that
(a) LLM detectors are *selectively* strong (not uniformly weak), (b) the ≈0.63 recall
ceiling is a *model-capability bound* (not a corpus artifact), and (c) the ceiling is
breakable by LLM × static-tool fusion (measured fused F1 = 0.827).

## Repository layout

```
CTBench-PQ/
├── data/                    # benchmark corpus (JSONL, see schema below)
│   ├── benchmark.jsonl      #   259-item master benchmark (TEST/DEV/TRAIN)
│   ├── hard_negatives.jsonl #   68 provably-CT-correct hard negatives
│   ├── pairs.jsonl          #   66 real defect–fix pairs (hunk-level)
│   ├── mutated_pairs.jsonl  #   125 synthetic mutations
│   └── commit_ledger.jsonl  #   provenance ledger (CVE → commit → hunk)
├── results/                 # per-detector prediction outputs (JSONL)
│   ├── benchmark_merged.jsonl    #   72-item merged split (released labels)
│   ├── benchmark_extended.jsonl  #   104-item extended TEST
│   ├── benchmark_pqc_v2.jsonl    #   PQC v2 non-Kyber items
│   └── e4_extended_<model>_s1.jsonl  #  per-detector predictions on extended set
├── analysis/                # reproducible analysis scripts
│   ├── verify_merged_ceiling.py   #  main-result verification
│   ├── recompute_extended.py      #  extended metrics + McNemar
│   ├── significance.py            #  pairwise significance (E4c)
│   ├── fdc_mi_measured_fusion.py  #  FDC-MI fusion closed form (measured)
│   └── tool_capability_frontier.py#  fusion reachability frontier
├── detectors.yaml           # exact detector environment (model/endpoint/temp/budget)
├── reproduce.sh             # one-shot reproduction entry point
└── Dockerfile               # locked toolchain (python 3.13 + MiKTeX + gcc 15.2)
```

## Data schema (JSONL, one object per line)

Common fields for every benchmark item:

| field | type | meaning |
|---|---|---|
| `item_id` | str | unique id, e.g. `S0006`, `D3-N0067` |
| `split` | str | `test` \| `dev` \| `train` |
| `label` | str | `defective` \| `clean` (released ground truth) |
| `defect_type` | str \| null | CT defect class (e.g. `secret_branch`, `table_access`, `compiler_mask`) |
| `defect_class` | str \| null | `compiler_induced` \| `semantic` \| ... (E6 taxonomy) |
| `non_ct_noise` | bool | true for non-CT semantic-migration noise (excluded from evaluation) |
| `origin` | str | `real_cve` \| `synthetic` \| `hard_negative` |
| `language` | str | `C` \| `Java` \| `Rust` \| `other` |
| `cve_id` | str \| null | associated CVE (if any) |
| `fix_commit` | str \| null | genuine fix commit hash |
| `label_confidence` | str | `exact` \| `medium` \| `low` (advisory specificity) |
| `code_before` / `code_after` | str | defective / fixed source snippet |

Per-detector prediction fields (`e4_extended_*.jsonl`): `item_id`, `model`, `strategy`,
`repeat`, `pred_found` (`true`/`false`/`null`), `raw_response`, `n_fail`.

## Ground-truth adjudication

The released labels follow the authoritative benchmark. The GT correction is documented
in `analysis/GT_judge_matrix.md`: 3 weak-truth items reclassified to clean
(S0075/S0129/S0134) and 12 non-CT semantic-migration-noise TEST items singled out via
`non_ct_noise`. All 36 remaining TEST defective items have `defect_type` confirmed (100%).
The label-confidence field marks items where the CVE advisory is not fully specific.

## Detector environment

See `detectors.yaml` for exact model IDs, hosting platforms, endpoints, temperature (0.0),
token budgets, timeouts, and prompt strategy. LLM detector model versions drift at the
provider; reproduction against this release should pin the provider state to the date in
`detectors.yaml` (`last_evaluated: 2026-11-12`).

## Reproduction

```bash
./reproduce.sh
```

This runs, in order: (1) leakage check, (2) merged-ceiling verification, (3) extended
metrics + McNemar, (4) FDC-MI fusion. Expected key values:

| metric | value |
|---|---|
| merged 70-item D1 F1 | 0.655 |
| extended 92 non-noise D1 F1 | 0.548 |
| extended 92 dots3-note-prev F1 | 0.622 |
| D3 (mock-rule-v1) Orig F1 | 0.250 |
| measured fused F1 (Binsec+dudect) | 0.827 |
| D1 recall ceiling (merged) | 0.633 |

## Public CI reproduction (GitHub Actions)

`./.github/workflows/reproduce.yml` re-runs the five-step pipeline
(`reproduce.sh`: leakage check, merged ceiling, extended recompute, measured
fusion, then the self-checking `analysis/verify_anchors.py` that asserts all
six anchors above) on fresh GitHub-hosted runners (`ubuntu-latest` +
`macos-latest` matrix) on every push to `master`/`main` and on every pull
request. This provides a public, independently-hosted verification that any
account can inspect, as a weaker substitute for a true third-party run.

**Executed runs** (2026-11-18):
- Commit `f254c22` on `master`, run `#44230159660` — **completed successfully**
  in 16s on `ubuntu-latest`.
- Commit `d8c8029` on `master`, run `#44233550798` — **completed successfully**
  in 10s on `ubuntu-latest`.
- Commit `9ac89a2` on `master`, run `#44241622940` — **completed successfully**
  in 9s on the **two-OS matrix** (`ubuntu-latest` + `macos-latest`).
In each case the job exit status 0, which by `verify_anchors.py`'s contract
(non-zero on any anchor miss), means all six anchors matched on every platform.

A first three-OS attempt (commit `cbbd0c5`, run `#44240772791`) additionally
showed that a `windows-latest` job fails at the `bash reproduce.sh` step (a
Git-Bash / `python3` path limitation on the Windows runner), so the matrix is
restricted to the two Unix platforms that pass; Windows is an explicitly
documented follow-up (needs an explicit `shell: bash` step and a `python3`
alias).


## Notes

- The D2/D2b variant `Atria-Dawn-Preview` merged-benchmark predictions are not released
  with the corpus; `Atria-Dawn` serves as the same-platform representative.
- Three rate-limited models (HTTP 429: deepseek-v4-flash-vision, glm-5.3, qwen3.8-27b)
  fall outside the measured scope and are disclosed, not silently omitted.
- The D3-N0067/D3-N0068 PQC hard negatives could not be evaluated by the shared-platform
  detectors (HTTP 429); they remain in the released benchmark as clean hard negatives.

## Tool-calibration extension (M2)

The 27-item tool calibration (24 microbenchmark + 3 Kyber) is reproduced by
`tool_baseline/combine_tool_baseline_all.py` (reads `tool_baseline/mb2_results_final.jsonl`,
`tool_baseline/dudect_fixtures/dudect_results_final.jsonl`,
`tool_baseline/dudect_fixtures_all/dudect_all_final.txt`,
`tool_baseline/microbench/manifest.json`). Expected (source-level GT):

| metric | value |
|---|---|
| R_t | 0.846 (TP=11 / FN=2) |
| P_t | 1.000 (FP=0 / TN=14) |
| Clopper-Pearson lower bound R_t | 0.546 |
| Clopper-Pearson lower bound P_t | 0.715 |

Note: under `gcc -O2` on x86-64 every source-defective fixture is compiled to
constant time (dudect returns CT on all 24 microbenchmark items and on KyberSlash),
so the platform-level calibration contains no actual-leak positive sample and the
platform-level R_t is un-estimable; the measured R_t is a source/static-view caliber.
