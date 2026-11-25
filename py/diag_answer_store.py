
# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
db = sqlite3.connect(ROOT / "data" / "fitness_qa.db")
db.row_factory = sqlite3.Row

print(f"{'模型':<22}{'rag':<5}{'总条':>6}{'空答案':>8}{'均长':>8}{'均分':>8}  error_msg")
print("-" * 95)
for t in db.execute(
    "SELECT id, model_name, rag_enabled, error_msg FROM tasks "
    "WHERE batch='v3_60' ORDER BY model_name, rag_enabled"
):
    r = db.execute("""
        SELECT COUNT(*) n,
               SUM(CASE WHEN answer IS NULL OR answer='' THEN 1 ELSE 0 END) empty,
               AVG(LENGTH(COALESCE(answer,''))) avg_len,
               AVG(score_overall) avg_score
        FROM results WHERE task_id=?
    """, (t["id"],)).fetchone()
    err = (t["error_msg"] or "")[:40]
    print(f"{t['model_name']:<22}{t['rag_enabled']:<5}{r['n']:>6}"
          f"{r['empty']:>8}{r['avg_len']:>8.0f}{r['avg_score']:>8.3f}  {err}")