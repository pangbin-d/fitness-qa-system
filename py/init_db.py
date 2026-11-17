# -*- coding: utf-8 -*-
"""
数据库初始化与基础读写封装（SQLite 3）

用法：
    python3 py/init_db.py           # 建表 + 同步配置（幂等，可反复跑）
    python3 py/init_db.py --check   # 只体检，不建表

设计要点：
    1. 所有写操作走同一个 get_conn 上下文管理器，异常自动回滚
    2. 外键约束每次连接都打开（SQLite 默认关闭）
    3. configs 表的值以 py/config.py 为准，每次 init 都覆盖同步
    4. 题目/结果里的 JSON 字段（kb_refs / kb_related / retrieved_ids）
       统一在读写层做序列化，调用方直接传 list
"""
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (DATA_VERSION, EVAL, RAG, MODELS_SEED,
                    DEFAULT_MODEL, DEFAULT_REVIEWER, PROVIDERS)
from scoring import EQUAL_WEIGHTS, score_overall

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "fitness_qa.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"


# ============================================================
# 连接管理
# ============================================================
@contextmanager
def get_conn():
    """连接上下文管理器：正常提交、异常回滚、始终关闭。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 外键约束 SQLite 默认关闭，每个连接都要重新开
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL：读写不互相阻塞，是后面加 FastAPI 时避免 database is locked 的关键
    conn.execute("PRAGMA journal_mode = WAL")
    # WAL 模式下 NORMAL 已经足够安全，比 FULL 快很多
    conn.execute("PRAGMA synchronous = NORMAL")
    # 遇到写锁时最多等 5 秒再报错，而不是立刻失败
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _json_load(value, default):
    """把库里的 JSON 字符串安全转回 Python 对象。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _json_dump(value):
    """把 Python 对象转成库里的 JSON 字符串，中文不转义。"""
    return json.dumps(value, ensure_ascii=False)


# ============================================================
# 初始化
# ============================================================
def init_db():
    """执行 schema.sql 建表（幂等），然后同步 config.py 的配置。"""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema 文件不存在：{SCHEMA_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    sync_configs()
    seed_models()
    return DB_PATH


def sync_configs():
    """把 py/config.py 的参数写进 configs 表，覆盖旧值。"""
    items = [
        ("data_version_kb", DATA_VERSION["kb"], "知识库数据版本"),
        ("data_version_qb", DATA_VERSION["qb"], "题库数据版本"),
        ("model_name", DEFAULT_MODEL, "当前默认被测模型 key"),
        ("reviewer_model", DEFAULT_REVIEWER, "评审模型 key（统一一个，不得与被测重复）"),
        ("temperature", "0.3", "被测模型采样温度"),
        ("scoring_rule", EVAL["scoring_rule"], "评分口径"),
        ("score_weights", _json_dump(EQUAL_WEIGHTS),
         "主指标权重（等权）；加权对照方案见 config.py 的 EVAL[weight_variants]"),
        ("repeat_times", str(EVAL["repeat_times"]), "每题重复运行次数"),
        ("rag_top_k", str(RAG["top_k"]), "检索返回条数"),
        ("embedding_model", RAG["embedding_model"], "向量模型"),
        ("chunk_size", str(RAG["chunk_size"]), "切块长度"),
        ("chunk_overlap", str(RAG["chunk_overlap"]), "切块重叠"),
    ]
    with get_conn() as conn:
        for key, value, note in items:
            conn.execute(
                """
                INSERT INTO configs(key, value, note, updated_at)
                VALUES (?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (key, value, note),
            )
    return len(items)


# ============================================================
# 配置读写
# ============================================================
def get_config(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM configs WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_config(key, value, note=None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO configs(key, value, note, updated_at)
            VALUES (?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                note = COALESCE(excluded.note, configs.note),
                updated_at = excluded.updated_at
            """,
            (key, str(value), note),
        )


def get_all_configs():
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value, note FROM configs ORDER BY key").fetchall()
    return {r["key"]: r["value"] for r in rows}


# ============================================================
# questions 题目表
# ============================================================
def upsert_question(qid, batch, topic, question, ref_points, score_points,
                    qtype="kb", difficulty=None, kb_refs=None,
                    kb_related=None, is_in_kb=None, aspect=None):
    """插入或更新一道题。qtype 决定 is_in_kb 的默认值。"""
    if is_in_kb is None:
        is_in_kb = 1 if qtype == "kb" else 0

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO questions
                (id, batch, topic, aspect, qtype, difficulty, question,
                 ref_points, score_points, kb_refs, kb_related, is_in_kb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                batch        = excluded.batch,
                topic        = excluded.topic,
                aspect       = excluded.aspect,
                qtype        = excluded.qtype,
                difficulty   = excluded.difficulty,
                question     = excluded.question,
                ref_points   = excluded.ref_points,
                score_points = excluded.score_points,
                kb_refs      = excluded.kb_refs,
                kb_related   = excluded.kb_related,
                is_in_kb     = excluded.is_in_kb
            """,
            (qid, batch, topic, aspect, qtype, difficulty, question,
             ref_points, score_points,
             _json_dump(kb_refs or []), _json_dump(kb_related or []), is_in_kb),
        )


def upsert_questions(items):
    """批量写入，items 是 dict 列表。返回写入条数。"""
    for it in items:
        upsert_question(**it)
    return len(items)


def get_question(qid):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    return _row_to_question(row) if row else None


def list_questions(batch=None, topic=None, qtype=None):
    sql = "SELECT * FROM questions WHERE 1=1"
    params = []
    if batch:
        sql += " AND batch = ?"
        params.append(batch)
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if qtype:
        sql += " AND qtype = ?"
        params.append(qtype)
    sql += " ORDER BY id"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_question(r) for r in rows]


def _row_to_question(row):
    d = dict(row)
    d["kb_refs"] = _json_load(d.get("kb_refs"), [])
    d["kb_related"] = _json_load(d.get("kb_related"), [])
    return d


def question_stats(batch=None):
    """统计题量分布：按 batch / topic / qtype。"""
    where = "WHERE batch = ?" if batch else ""
    params = (batch,) if batch else ()
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM questions {where}", params).fetchone()["n"]
        by_topic = conn.execute(
            f"SELECT topic, COUNT(*) AS n FROM questions {where} GROUP BY topic ORDER BY n DESC", params
        ).fetchall()
        by_type = conn.execute(
            f"SELECT qtype, COUNT(*) AS n FROM questions {where} GROUP BY qtype ORDER BY n DESC", params
        ).fetchall()
    return {
        "total": total,
        "by_topic": {r["topic"]: r["n"] for r in by_topic},
        "by_qtype": {r["qtype"]: r["n"] for r in by_type},
    }


# ============================================================
# tasks 任务表
# ============================================================
def create_task(batch, prompt_version, model_name, rag_enabled=0,
                total=0, config_json=None, task_id=None,
                experiment_id=None, reviewer_model=None, model_version=None):
    if task_id is None:
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tasks
                (id, experiment_id, batch, prompt_version, model_name,
                 model_version, reviewer_model, rag_enabled,
                 config_json, status, total, progress, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, 0, datetime('now','localtime'))
            """,
            (task_id, experiment_id, batch, prompt_version, model_name,
             model_version, reviewer_model, int(rag_enabled),
             config_json, total),
        )
    return task_id


def update_task(task_id, status=None, progress=None, error_msg=None,
                model_version=None, finished=False):
    sets, params = [], []
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if progress is not None:
        sets.append("progress = ?")
        params.append(progress)
    if error_msg is not None:
        sets.append("error_msg = ?")
        params.append(error_msg)
    if model_version is not None:
        sets.append("model_version = ?")
        params.append(model_version)
    if finished:
        sets.append("finished_at = datetime('now','localtime')")
    if not sets:
        return

    params.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)


def get_task(task_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(batch=None, status=None):
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if batch:
        sql += " AND batch = ?"
        params.append(batch)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# results 结果表
# ============================================================
def insert_result(task_id, question_id, answer=None, run_index=1,
                  scores=None, review_raw=None, retrieved_ids=None,
                  latency_ms=None, error=None, reviewer_model=None):
    """
    写入单题结果。scores 是四维分 dict，综合分由代码加权计算。

    安全性否决：安全性 <= EVAL["safety_veto"]["threshold"] 时，
    总分被压到 cap 以内，并置 safety_vetoed=1 供分析时单独统计。
    """
    scores = scores or {}
    overall, vetoed = score_overall(scores)
    vetoed = int(vetoed)

    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO results
                (task_id, question_id, run_index, answer,
                 score_accuracy, score_complete, score_safety, score_relevance,
                 score_overall, safety_vetoed, reviewer_model, review_raw,
                 retrieved_ids, latency_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, question_id, run_index, answer,
             scores.get("准确性"), scores.get("完整性"),
             scores.get("安全性"), scores.get("相关性"),
             overall, vetoed, reviewer_model, review_raw,
             _json_dump(retrieved_ids or []), latency_ms, error),
        )
        return cur.lastrowid


def get_results(task_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE task_id = ? ORDER BY question_id, run_index",
            (task_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["retrieved_ids"] = _json_load(d.get("retrieved_ids"), [])
        out.append(d)
    return out


def recall_hit_rate(task_id):
    """
    召回命中率：只按 kb_refs 算，kb_related 不算。
    命中定义：本题 retrieved_ids 与 kb_refs 有交集。
    返回 (命中题数, 可评估题数, 命中率)。超纲题无 kb_refs，不参与统计。
    """
    results = get_results(task_id)
    hit = total = 0
    for r in results:
        q = get_question(r["question_id"])
        if not q or not q["kb_refs"]:
            continue
        total += 1
        if set(r["retrieved_ids"]) & set(q["kb_refs"]):
            hit += 1
    return hit, total, (hit / total if total else 0.0)


# ============================================================
# snapshots 快照表
# ============================================================
def save_snapshot(task_id, metrics, snapshot_id=None, batch=None,
                  prompt_version=None, model_name=None,
                  rag_enabled=0, data_version=None, experiment_id=None,
                  reviewer_model=None, scoring_rule=None):
    task = get_task(task_id) or {}
    if snapshot_id is None:
        snapshot_id = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO snapshots
                (id, task_id, experiment_id, batch, prompt_version, model_name,
                 reviewer_model, rag_enabled, data_version, scoring_rule,
                 metrics_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (snapshot_id, task_id,
             experiment_id or task.get("experiment_id"),
             batch or task.get("batch"),
             prompt_version or task.get("prompt_version"),
             model_name or task.get("model_name"),
             reviewer_model or task.get("reviewer_model"),
             int(rag_enabled if rag_enabled is not None else task.get("rag_enabled", 0)),
             data_version or DATA_VERSION["kb"],
             scoring_rule or EVAL["scoring_rule"],
             _json_dump(metrics)),
        )
    return snapshot_id


def get_snapshot(snapshot_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["metrics_json"] = _json_load(d.get("metrics_json"), {})
    return d


# ============================================================
# models 模型配置
# ============================================================
def seed_models():
    """
    把 config.MODELS_SEED 写入 models 表（按 model_key upsert，幂等）。

    写入前做一次冲突校验：同一个 model_id 不能同时出现在
    candidate 和 reviewer 两个角色里，否则等于自己评自己。
    """
    by_mid = {}
    for m in MODELS_SEED:
        by_mid.setdefault(m["model_id"], set()).add(m["role"])
    conflicts = {mid: roles for mid, roles in by_mid.items()
                 if len(roles) > 1}
    if conflicts:
        raise ValueError(
            "模型角色冲突：以下 model_id 同时被用作被测和评审，"
            f"违反异模型评审原则 -> {conflicts}"
        )

    n = 0
    with get_conn() as conn:
        for m in MODELS_SEED:
            prov = PROVIDERS.get(m["provider"], {})
            conn.execute(
                """
                INSERT INTO models
                    (model_key, display_name, provider, base_url, api_key_env,
                     model_id, role, temperature, enabled, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(model_key) DO UPDATE SET
                    display_name = excluded.display_name,
                    provider     = excluded.provider,
                    base_url     = excluded.base_url,
                    api_key_env  = excluded.api_key_env,
                    model_id     = excluded.model_id,
                    role         = excluded.role,
                    temperature  = excluded.temperature,
                    note         = excluded.note
                """,
                (m["model_key"], m["display_name"], m["provider"],
                 prov.get("base_url", ""), prov.get("api_key_env", ""),
                 m["model_id"], m["role"], m.get("temperature", 0.3),
                 m.get("note")),
            )
            n += 1

        # 种子之外的旧模型只停用不删除，保留历史任务的引用完整性
        keys = tuple(m["model_key"] for m in MODELS_SEED)
        placeholders = ",".join("?" * len(keys))
        conn.execute(
            f"UPDATE models SET enabled = 0 WHERE model_key NOT IN ({placeholders})",
            keys,
        )
    return n


def list_models(role=None, enabled_only=True):
    sql = "SELECT * FROM models WHERE 1=1"
    params = []
    if role:
        sql += " AND role = ?"
        params.append(role)
    if enabled_only:
        sql += " AND enabled = 1"
    sql += " ORDER BY role, model_key"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_model(model_key):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM models WHERE model_key = ?", (model_key,)
        ).fetchone()
    return dict(row) if row else None


def get_reviewer_model():
    """取当前生效的评审模型。有多个时取 model_key 最小的那个，保证确定性。"""
    rows = list_models(role="reviewer")
    if not rows:
        raise RuntimeError("models 表里没有可用的评审模型，先跑 seed_models()")
    return rows[0]


def check_model_role_conflict(candidate_keys, reviewer_key):
    """
    校验：评审模型不得出现在被测名单中。
    返回 (ok, message)。
    """
    if reviewer_key in candidate_keys:
        return False, f"评审模型 {reviewer_key} 出现在被测名单里，违反异模型评审原则"
    rev = get_model(reviewer_key)
    if not rev:
        return False, f"评审模型 {reviewer_key} 不存在于 models 表"
    if rev["role"] != "reviewer":
        return False, f"模型 {reviewer_key} 的 role 是 {rev['role']}，不是 reviewer"
    return True, "校验通过"


# ============================================================
# prompts 提示词版本
# ============================================================
def upsert_prompt(name, version, content, changelog=None, is_active=0):
    """写入或更新一个提示词版本。历史版本只增不改内容。"""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO prompts(name, version, content, changelog, is_active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name, version) DO UPDATE SET
                content   = excluded.content,
                changelog = excluded.changelog,
                is_active = excluded.is_active
            """,
            (name, version, content, changelog, int(is_active)),
        )
    if is_active:
        set_active_prompt(name, version)
    return f"{name}:{version}"


def set_active_prompt(name, version):
    """把某个版本设为该 name 下的默认版本，其余置 0。"""
    with get_conn() as conn:
        conn.execute("UPDATE prompts SET is_active = 0 WHERE name = ?", (name,))
        conn.execute(
            "UPDATE prompts SET is_active = 1 WHERE name = ? AND version = ?",
            (name, version),
        )


def get_prompt(name, version=None):
    """取提示词。version 为空时取 is_active=1 的版本。"""
    with get_conn() as conn:
        if version:
            row = conn.execute(
                "SELECT * FROM prompts WHERE name = ? AND version = ?",
                (name, version),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM prompts WHERE name = ? AND is_active = 1 "
                "ORDER BY id DESC LIMIT 1", (name,),
            ).fetchone()
    return dict(row) if row else None


def list_prompts(name=None):
    sql = "SELECT id, name, version, changelog, is_active, created_at FROM prompts"
    params = []
    if name:
        sql += " WHERE name = ?"
        params.append(name)
    sql += " ORDER BY name, id"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ============================================================
# knowledge 知识库条目
# ============================================================
def upsert_knowledge(kid, topic, content, aspect=None,
                     source_title=None, source_page=None, source_note=None,
                     status="active", data_version=None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO knowledge
                (id, topic, aspect, content, source_title, source_page,
                 source_note, status, data_version, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(id) DO UPDATE SET
                topic        = excluded.topic,
                aspect       = excluded.aspect,
                content      = excluded.content,
                source_title = excluded.source_title,
                source_page  = excluded.source_page,
                source_note  = excluded.source_note,
                status       = excluded.status,
                data_version = excluded.data_version,
                updated_at   = datetime('now','localtime')
            """,
            (kid, topic, aspect, content, source_title, source_page,
             source_note, status, data_version),
        )


def list_knowledge(topic=None, status=None, limit=0):
    sql = "SELECT * FROM knowledge WHERE 1=1"
    params = []
    if topic:
        sql += " AND topic = ?"
        params.append(topic)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def knowledge_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM knowledge").fetchone()["n"]
        by_topic = {r["topic"]: r["n"] for r in conn.execute(
            "SELECT topic, COUNT(*) AS n FROM knowledge GROUP BY topic").fetchall()}
        chunks = conn.execute("SELECT COUNT(*) AS n FROM kb_chunks").fetchone()["n"]
    return {"total": total, "by_topic": by_topic, "chunks": chunks}


# ============================================================
# 体检
# ============================================================
def health_check():
    """打印表结构、行数、配置，用于确认初始化是否正常。"""
    if not DB_PATH.exists():
        print(f"[!] 数据库不存在：{DB_PATH}")
        print("    先跑 python3 py/init_db.py")
        return False

    print(f"数据库：{DB_PATH}")
    print(f"大小  ：{DB_PATH.stat().st_size / 1024:.1f} KB")
    print()

    tables = ["questions", "models", "prompts", "tasks", "results",
              "snapshots", "knowledge", "kb_chunks", "configs"]
    with get_conn() as conn:
        print("=== 表行数 ===")
        for t in tables:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            print(f"  {t:12s} {n:>6d}")

        print()
        print("=== questions 表结构 ===")
        cols = conn.execute("PRAGMA table_info(questions)").fetchall()
        for c in cols:
            print(f"  {c['name']:16s} {c['type']:8s} notnull={c['notnull']} default={c['dflt_value']}")

    print()
    print("=== configs ===")
    for k, v in get_all_configs().items():
        print(f"  {k:20s} = {v}")

    print()
    print("=== 题量分布 ===")
    stats = question_stats()
    print(f"  总题数：{stats['total']}")
    if stats["total"]:
        print(f"  按 topic：{stats['by_topic']}")
        print(f"  按 qtype：{stats['by_qtype']}")
    else:
        print("  （题库为空，等导入旧 30 题 / 新建新 60 题）")

    return True


def main():
    if "--check" in sys.argv:
        health_check()
        return

    path = init_db()
    print(f"[OK] 数据库已就绪：{path}")
    print()
    health_check()


if __name__ == "__main__":
    main()
