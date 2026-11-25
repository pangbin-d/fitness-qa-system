
# -*- coding: utf-8 -*-
"""一次性导出所有模型的 off/on 对比结果到 data/ 下。"""
import sqlite3, subprocess, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
db = sqlite3.connect(ROOT / "data" / "fitness_qa.db")
db.row_factory = sqlite3.Row

rows = list(db.execute(
    "SELECT id, model_name, rag_enabled FROM tasks "
    "WHERE batch='v3_60' AND status='completed' ORDER BY model_name, rag_enabled"
))

pairs = {}
for r in rows:
    key = "on" if r["rag_enabled"] else "off"
    pairs.setdefault(r["model_name"], {})[key] = r["id"]

out_dir = ROOT / "data"
env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

for model, p in sorted(pairs.items()):
    if "off" not in p or "on" not in p:
        print(f"[!] {model} 缺一组，跳过")
        continue
    for run in (1, 2, 3):
        out = out_dir / f"cmp_{model}_run{run}.txt"
        cmd = [sys.executable, str(ROOT / "py" / "compare_results.py"),
               "-b", p["off"], "-c", p["on"], "--run-index", str(run)]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        if r.returncode != 0:
            print(f"[x] {model} run{run} 失败: {r.stderr[:200]}")
            continue
        out.write_text(r.stdout, encoding="utf-8")
        print(f"[ok] {out.name}")

print("\n完成，文件在 data/ 下")