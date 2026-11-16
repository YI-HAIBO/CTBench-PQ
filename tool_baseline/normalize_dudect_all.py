# -*- coding: utf-8 -*-
"""归一化 dudect 24 项 microbench 批量跑测结果，生成确定性 final 文件。

背景：VM 上批处理被并发启动两次，dudect_all_results.txt 出现重复/交错行，
其中 c09/d03/d05 各出现一个 rc=0 sec=0 的伪行（并发写错位），与真实 rc=124 冲突。
这 3 项已单次干净重跑（dudect_rerun.txt）确认 rc=124（CT）。

归一化规则：
  1. 若 item 在 rerun 里 -> 采用 rerun 判定（单次干净，权威）。
  2. 否则在 all 里该 item 若出现多次且 rc 一致 -> 采用该 rc；
     若出现多次且 rc 不一致（理论上不应再发生）-> 标记 CONFLICT 并保留众数。
输出：dudect_all_final.txt（每项一行 RESULT <name> rc=... sec=...（取最大 sec 作为代表））。
"""
import re, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALL = HERE / "dudect_fixtures_all" / "dudect_all_results.txt"
RERUN = HERE / "dudect_fixtures_all" / "dudect_rerun.txt"
OUT = HERE / "dudect_fixtures_all" / "dudect_all_final.txt"


def parse(path: Path) -> dict:
    """name -> [(rc, sec), ...]"""
    d = collections.defaultdict(list)
    if not path.exists():
        return d
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"RESULT (\w+) rc=(\d+) sec=(\d+)", line.strip())
        if m:
            d[m.group(1)].append((int(m.group(2)), int(m.group(3))))
    return d


def main():
    all_r = parse(ALL)
    rerun_r = parse(RERUN)
    names = sorted(set(all_r) | set(rerun_r))
    lines = []
    conflicts = []
    for name in names:
        if name in rerun_r:
            rc, sec = rerun_r[name][-1]  # 重跑权威（单次干净）
            src = "rerun"
        else:
            entries = all_r[name]
            rcs = [r for r, s in entries]
            cnt = collections.Counter(rcs)
            rc = cnt.most_common(1)[0][0]
            sec = max(s for r, s in entries)
            src = "all"
            if len(cnt) > 1:
                conflicts.append((name, cnt))
        lines.append(f"RESULT {name} rc={rc} sec={sec}  # {src}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} items)")
    if conflicts:
        print("CONFLICT (resolved by mode):")
        for name, cnt in conflicts:
            print(f"  {name}: {dict(cnt)}")
    else:
        print("no residual conflicts")


if __name__ == "__main__":
    main()
