# -*- coding: utf-8 -*-
"""
v3_60 横向对比汇总 —— 输出三张表
    表1 主表：模型 × RAG 的四维均分、overall、标准差、失败数、否决数
    表2 RAG 增益：每个模型 on - off 的逐维 delta
    表3 排名：按 overall 排序，含稳定性
"""
import sqlite3
from pathlib import Path
from collections import defaultdict

DB = Path(__file__).parent.parent / "data" / "fitness_qa.db"
OUT = Path(__file__).parent.parent / "data" / "summary_v3_60.txt"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

# 每个 (model, rag) 只取最新一个 completed task，避免重复跑导致重复计数
latest = {}
for t in con.execute("""
    SELECT id, model_name, rag_enabled FROM tasks
    WHERE batch='v3_60' AND status='completed' ORDER BY created_at
"""):
    latest[(t["model_name"], t["rag_enabled"])] = t["id"]

data = defaultdict(list)
for (model, rag), tid in latest.items():
    for r in con.execute("""
        SELECT question_id, run_index, score_accuracy, score_complete,
               score_safety, score_relevance, score_overall,
               safety_vetoed, error
        FROM results WHERE task_id=?
    """, (tid,)):
        data[(model, rag)].append(dict(r))

def stats(rs):
    ok = [r for r in rs if not r["error"]]
    n = len(ok)
    if n == 0:
        return None
    def avg(k):
        return sum(r[k] for r in ok) / n
    ov = [r["score_overall"] for r in ok]
    mean = sum(ov) / n
    std = (sum((x - mean) ** 2 for x in ov) / n) ** 0.5
    return {
        "n": n, "err": len(rs) - n,
        "veto": sum(1 for r in ok if r["safety_vetoed"]),
        "acc": avg("score_accuracy"), "comp": avg("score_complete"),
        "safe": avg("score_safety"), "rel": avg("score_relevance"),
        "ov": mean, "std": std,
    }

L = []
L.append("=" * 96)
L.append("表1  v3_60 横向对比主表（评审模型统一为 hy4-judge，提示词 v2_coach，每题 3 次）")
L.append("=" * 96)
L.append(f"{'模型':22}{'RAG':5}{'有效':>6}{'失败':>6}{'否决':>6}"
         f"{'准确性':>8}{'完整性':>8}{'安全性':>8}{'相关性':>8}{'overall':>10}{'标准差':>9}")
for (model, rag) in sorted(data.keys()):
    s = stats(data[(model, rag)])
    if not s:
        L.append(f"{model:22}{'on' if rag else 'off':5}  无有效数据")
        continue
    L.append(f"{model:22}{'on' if rag else 'off':5}{s['n']:6}{s['err']:6}{s['veto']:6}"
             f"{s['acc']:8.2f}{s['comp']:8.2f}{s['safe']:8.2f}{s['rel']:8.2f}"
             f"{s['ov']:10.4f}{s['std']:9.4f}")

L.append("")
L.append("=" * 96)
L.append("表2  RAG 增益（on - off，正值表示加 RAG 后变好）")
L.append("=" * 96)
L.append(f"{'模型':22}{'准确性':>9}{'完整性':>9}{'安全性':>9}{'相关性':>9}{'overall':>10}")
models = sorted({m for (m, _) in data.keys()})
for model in models:
    off = stats(data.get((model, 0), []))
    on = stats(data.get((model, 1), []))
    if not off or not on:
        L.append(f"{model:22}  缺 off 或 on，无法计算")
        continue
    L.append(f"{model:22}{on['acc']-off['acc']:+9.3f}{on['comp']-off['comp']:+9.3f}"
             f"{on['safe']-off['safe']:+9.3f}{on['rel']-off['rel']:+9.3f}"
             f"{on['ov']-off['ov']:+10.4f}")

L.append("")
L.append("=" * 96)
L.append("表3  按 overall 排名（RAG off 基线）")
L.append("=" * 96)
ranked = []
for model in models:
    s = stats(data.get((model, 0), []))
    if s:
        ranked.append((model, s))
for i, (model, s) in enumerate(sorted(ranked, key=lambda x: -x[1]["ov"]), 1):
    L.append(f"{i}. {model:24}overall={s['ov']:.4f}  标准差={s['std']:.4f}  "
             f"失败={s['err']}  否决={s['veto']}")

text = "\n".join(L)
print(text)
OUT.write_text(text, encoding="utf-8")
print(f"\n已导出 -> {OUT}")