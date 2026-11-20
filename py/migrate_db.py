# -*- coding: utf-8 -*-
"""
数据库结构迁移：把旧版五表库升级到新版九表结构。

用法：
    python3 py/migrate_db.py          # 执行迁移
    python3 py/migrate_db.py --check  # 只检查，不写库

做的事：
    1. 执行 schema.sql，把缺失的新表建出来（models/prompts/knowledge/kb_chunks）
    2. 给已存在的旧表补新列（SQLite 的 ADD COLUMN 不支持 IF NOT EXISTS，先查 pragma）
    3. 回填 configs 里新增的键

特点：
    - 幂等，跑多少次结果都一样
    - 不删任何数据，只加结构
    - 旧列不改名、不改类型
"""
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "fitness_qa.db"
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"


def _table_list(conn):
    """返回用户表名列表（排除 sqlite_ 系统表）。"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows if not r[0].startswith("sqlite_")]


def _columns(conn, table):
    """返回表的现有列名集合。表不存在时返回空集。"""
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _add_column_if_missing(conn, table, column, ddl, log):
    """SQLite 不支持 ADD COLUMN IF NOT EXISTS，只能先查后加。"""
    cols = _columns(conn, table)
    if not cols:
        log.append(f"  跳过 {table}.{column}：表 {table} 不存在（由 schema.sql 新建）")
        return False
    if column in cols:
        log.append(f"  跳过 {table}.{column}：已存在")
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    log.append(f"  ✅ 新增 {table}.{column} {ddl}")
    return True


# 需要补齐的列：(表名, 列名, 类型定义, 说明)
PENDING_COLUMNS = [
    ("tasks", "experiment_id", "TEXT",
     "实验编号，多模型横向评测用它对若干条 task 分组"),
    ("tasks", "reviewer_model", "TEXT",
     "评审模型 key，评审换代后分数不可比，必须留痕"),
    ("results", "reviewer_model", "TEXT",
     "本次打分用的评审模型 key"),
    ("snapshots", "experiment_id", "TEXT",
     "实验编号，便于按实验聚合查询"),
    ("snapshots", "reviewer_model", "TEXT",
     "快照对应的评审模型 key"),
    ("snapshots", "scoring_rule", "TEXT",
     "评分口径 simple_average / weighted_with_veto，跨口径不可直接比较"),
]

# 新增索引（旧库升级后补建）
PENDING_INDEXES = [
    ("idx_t_experiment", "tasks(experiment_id)"),
    ("idx_s_experiment", "snapshots(experiment_id)"),
    ("idx_m_role", "models(role)"),
    ("idx_p_name", "prompts(name)"),
    ("idx_k_topic", "knowledge(topic)"),
    ("idx_k_status", "knowledge(status)"),
    ("idx_c_kid", "kb_chunks(knowledge_id)"),
]

# 需要回填的配置项（键, 值, 说明）
PENDING_CONFIGS = [
    ("reviewer_model", "qwen-72b-judge", "评审模型 key（统一一个，不得与被测重复）"),
    ("scoring_rule", "weighted_with_veto", "评分口径"),
    ("score_weights",
     '{"准确性":0.25,"完整性":0.25,"安全性":0.25,"相关性":0.25}',
     "主指标权重（等权）"),
]


def migrate(check_only=False):
    log = []
    if not DB_PATH.exists():
        log.append(f"数据库不存在：{DB_PATH}")
        log.append("请先跑 python3 py/init_db.py 建库")
        return log, 1

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    log.append(f"目标库：{DB_PATH}")
    tables_before = _table_list(conn)
    log.append(f"迁移前表：{tables_before}")

    # 步骤 1：补列
    #   必须先于 schema.sql：schema 里的 CREATE INDEX 引用了新列，
    #   旧表没有该列时建索引会直接报 no such column。
    log.append("步骤 1：补列")
    changed = 0
    for table, column, ddl, note in PENDING_COLUMNS:
        if check_only:
            cols = _columns(conn, table)
            need = bool(cols) and column not in cols
            log.append(f"  {'⚠️ 待加' if need else '  已有'} {table}.{column} —— {note}")
            changed += int(need)
        else:
            changed += int(_add_column_if_missing(conn, table, column, ddl, log))

    # 步骤 2：建缺失的表 + 索引（schema.sql 全是 IF NOT EXISTS，对已有表无副作用）
    if not check_only:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        log.append("步骤 2：已执行 schema.sql（补齐缺失的表与索引）")
    else:
        log.append("步骤 2：--check 模式跳过 schema.sql")

    # 步骤 3：补索引（schema.sql 已覆盖，这里只做兜底检查）
    log.append("步骤 3：补索引")
    for idx_name, target in PENDING_INDEXES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (idx_name,)
        ).fetchone()
        if exists:
            log.append(f"  跳过 {idx_name}：已存在")
            continue
        if check_only:
            log.append(f"  ⚠️ 待建 {idx_name} ON {target}")
            continue
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {target}")
            log.append(f"  ✅ 新建 {idx_name} ON {target}")
        except sqlite3.OperationalError as e:
            log.append(f"  ⚠️ 建索引失败 {idx_name}：{e}")

    # 步骤 4：回填配置
    log.append("步骤 4：回填 configs")
    for key, value, note in PENDING_CONFIGS:
        row = conn.execute("SELECT value FROM configs WHERE key=?", (key,)).fetchone()
        if row:
            log.append(f"  跳过 {key}：已存在（值={row[0]}）")
            continue
        if check_only:
            log.append(f"  ⚠️ 待补 {key} = {value}")
            continue
        conn.execute(
            "INSERT INTO configs(key, value, note, updated_at) "
            "VALUES (?, ?, ?, datetime('now','localtime'))",
            (key, value, note),
        )
        log.append(f"  ✅ 补入 {key} = {value}")

    if check_only:
        conn.rollback()
        log.append("\n--check 模式：所有改动已回滚，库未变更")
    else:
        conn.commit()
        log.append(f"\n迁移完成，共新增 {changed} 个列")
        log.append(f"迁移后表：{_table_list(conn)}")

    conn.close()
    return log, 0


def main():
    check_only = "--check" in sys.argv
    log, code = migrate(check_only=check_only)
    print("\n".join(log))
    sys.exit(code)


if __name__ == "__main__":
    main()
