#!/usr/bin/env bash
# CTBench-PQ reproduction entry point (release v1.0)
# Usage: ./reproduce.sh
set -euo pipefail
PY="${PYTHON:-python3}"

echo "[1/4] Cross-set leakage check ..."
"$PY" analysis/significance.py

echo "[2/4] Merged-ceiling verification ..."
"$PY" analysis/verify_merged_ceiling.py

echo "[3/4] Extended metrics + McNemar ..."
"$PY" analysis/recompute_extended.py

echo "[4/4] FDC-MI fusion (measured) ..."
"$PY" analysis/fdc_mi_measured_fusion.py

echo
echo "Expected anchors: merged-70 D1 F1=0.655; extended-92 D1 F1=0.548;"
echo "                  dots3 F1=0.622; mock-rule Orig F1=0.250; fused F1=0.827;"
echo "                  D1 recall ceiling=0.633."
echo "Reproduction complete."
