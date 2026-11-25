# -*- coding: utf-8 -*-
"""跑一遍 v3_60 的 Recall@3，确认检索链路正常。"""
import sys, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'py'))
import embed_knowledge as ek

db = sqlite3.connect(ROOT / 'data' / 'fitness_qa.db')
rows = db.execute(
    "SELECT id, question, kb_refs FROM questions "
    "WHERE batch='v3_60' AND is_in_kb=1 ORDER BY id"
).fetchall()

hit = full = 0
zero, partial = [], []
for qid, q, rj in rows:
    refs = set(json.loads(rj))
    _, ids = ek.retrieve(q, top_k=3)
    got = refs & set(ids)
    if got:
        hit += 1
    if refs <= set(ids):
        full += 1
    if not got:
        zero.append(qid)
    elif not refs <= set(ids):
        partial.append((qid, sorted(refs - set(ids))))

n = len(rows)
print(f"Recall@3 (任一命中) = {hit}/{n} = {hit/n:.1%}")
print(f"全命中              = {full}/{n} = {full/n:.1%}")
print(f"零命中 {len(zero)} 道: {zero}")
print(f"部分命中 {len(partial)} 道: {partial}")