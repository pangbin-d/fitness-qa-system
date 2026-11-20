# -*- coding: utf-8 -*-
"""
回归对比 —— 两个 task 的逐题分数差异，一条 SQL 自连接搞定

用法：
    python3 py/compare_results.py --list
    python3 py/compare_results.py -b task_legacy_v1_baseline -c task_legacy_v2_coach
    python3 py/compare_results.py -b A -c B --top 10
    python3 py/compare_results.py -b A -c B --run-index 2

为什么用 JOIN 而不是两层 for 循环：
    循环版要把两边全查出来、在内存里按 question_id 建字典、再逐条比对。
    30 题无所谓，600 题就要把 1200 行全 load 进内存，还得自己处理
    「一边有一边没有」的情况。JOIN 版把配对交给 SQLite 的索引，
    只取配对结果，且 LEFT JOIN 天然能找出单边存在的题。

三个必须锁死的条件（少一个结果就废）：
    1. run_index        —— 同一题跑 3 次就有 3 行，不锁会拼成 9 行笛卡尔积，
                           平均分直接被算歪，而且不会报错，最阴的一种
    2. task_id          —— 不锁就变成全表自连接，行数是平方级
    3. reviewer_model   —— 评审换过人，两边分数不是一把尺子量出来的，
                           delta 只能看方向不能看绝对值

和老脚本（pythonProject AI/compare_results.py）的关系：
    那个是 M5 时期的文件驱动版，读两份 JSONL。本脚本是数据库版，
    两者结果应当一致 —— 老脚本跑出的 v1=4.7917 / v2=3.2167 就是本脚本的
    验收基准，对不上说明 SQL 写错了。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import init_db as db

# 维度字段 → 中文名，顺序决定报表列顺序
DIMENSIONS = [
    ("score_accuracy", "准确性"),
    ("score_complete", "完整性"),
    ("score_safety", "安全性"),
    ("score_relevance", "相关性"),
]

TOP_N = 5


# ============================================================
# 列出可对比的 task
# ============================================================
def list_tasks():
    """
    列出所有 task 及其题目数、结果行数。

    一眼能看出哪些 task 能配对：
        n_q 相同且都等于 30 的，才是完整可比的一对。
        n_q=2 的那几个是 11-16 调试时跑挂的，别拿去对比。
    """
    sql = """
    SELECT t.id, t.batch, t.prompt_version, t.model_name,
           t.reviewer_model, t.status, t.created_at,
           COUNT(DISTINCT r.question_id) AS n_q,
           COUNT(r.id)                   AS n_rows
    FROM tasks t
    LEFT JOIN results r ON r.task_id = t.id
    GROUP BY t.id
    ORDER BY t.created_at
    """
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(sql).fetchall()]

    print(f"{'task_id':52}{'题数':>6}{'结果':>6}  {'评审':<18}{'批次':<12}状态")
    print("-" * 118)
    for r in rows:
        note = "" if r["n_q"] else "   ← 无结果，不能对比"
        print(f"{r['id']:52}{r['n_q']:>6}{r['n_rows']:>6}  "
              f"{str(r['reviewer_model'] or '-'):<18}"
              f"{str(r['batch'] or '-'):<12}{r['status'] or '-'}{note}")
    print("-" * 118)
    print("提示：题数相同的一对才能完整配对，比如 v1_baseline 与 v2_coach 都是 30。")
    return rows


# ============================================================
# 对比前的可对比性检查
# ============================================================
def check_comparable(baseline, current):
    """
    对比前确认三件事，任何一件不满足都要报警。

    这三件事不查，delta 算出来是「看起来精确的废话」：
    数字很漂亮，但两个分数根本不在同一把尺子上。
    """
    warns = []

    with db.get_conn() as conn:
        # ---- 1. 两边都得有结果 ----
        for tid, label in ((baseline, "基线"), (current, "当前")):
            n = conn.execute(
                "SELECT COUNT(*) FROM results WHERE task_id = ?", (tid,)
            ).fetchone()[0]
            if n == 0:
                raise SystemExit(
                    f"[x] {label} task「{tid}」没有结果行，先跑 evaluate.py"
                )
            print(f"[i] {label} {tid}：{n} 行结果")

        # ---- 2. run_index 分布 ----
        for tid, label in ((baseline, "基线"), (current, "当前")):
            runs = [r[0] for r in conn.execute(
                "SELECT DISTINCT run_index FROM results WHERE task_id = ? ORDER BY run_index",
                (tid,),
            )]
            if runs != [1]:
                warns.append(
                    f"{label} run_index = {runs}（不是只有 1）。"
                    f"本次只取 run_index=1 的那一次；若要对比重复运行的均值，"
                    f"得改成 GROUP BY question_id 取 AVG"
                )

        # ---- 3. 评审模型是否一致 ----
        rev = {}
        for tid in (baseline, current):
            rev[tid] = [r[0] for r in conn.execute(
                "SELECT DISTINCT reviewer_model FROM results WHERE task_id = ?", (tid,)
            )]
        if rev[baseline] != rev[current]:
            warns.append(
                f"两边评审模型不同：基线 {rev[baseline]} vs 当前 {rev[current]}。"
                f"评审换代后分数不可比，delta 只能看方向不能看绝对值"
            )

        # ---- 4. 评分口径是否一致（从 snapshots 读，老数据可能没快照）----
        rules = {}
        for tid in (baseline, current):
            row = conn.execute(
                "SELECT scoring_rule FROM snapshots WHERE task_id = ? LIMIT 1", (tid,)
            ).fetchone()
            rules[tid] = row[0] if row else None
        if rules[baseline] != rules[current]:
            warns.append(
                f"两边评分口径不同：基线 {rules[baseline]} vs 当前 {rules[current]}。"
                f"simple_average（四维简单平均）与 weighted_with_veto（加权+安全否决）"
                f"不可直接比较"
            )

    if warns:
        print()
        for w in warns:
            print(f"[!] {w}")
        print()
    return warns


# ============================================================
# 核心：自连接
# ============================================================
def fetch_pairs(baseline, current, run_index=1):
    """
    一次自连接把两版结果配对取回。

    results 表出现两次：b 代表基线，c 代表当前。
    ON 条件同时锁 question_id、task_id、run_index，
    只留下「两边都有的题、且都是第 run_index 次」的那些行。

    排序按 overall 差值升序 —— 退步最多的排最前面，
    因为看回归报告时最想先知道「哪几道题变差了」。
    """
    sql = """
    SELECT
        b.question_id       AS question_id,
        q.topic             AS topic,
        q.qtype             AS qtype,
        q.question          AS question,
        b.run_index         AS b_run,
        c.run_index         AS c_run,
        b.score_accuracy    AS b_accuracy,
        b.score_complete    AS b_complete,
        b.score_safety      AS b_safety,
        b.score_relevance   AS b_relevance,
        b.score_overall     AS b_overall,
        b.safety_vetoed     AS b_vetoed,
        c.score_accuracy    AS c_accuracy,
        c.score_complete    AS c_complete,
        c.score_safety      AS c_safety,
        c.score_relevance   AS c_relevance,
        c.score_overall     AS c_overall,
        c.safety_vetoed     AS c_vetoed,
        c.review_raw        AS c_review
    FROM results b
    JOIN results c
      ON c.question_id = b.question_id
     AND c.task_id     = ?
     AND c.run_index   = ?
    JOIN questions q
      ON q.id = b.question_id
    WHERE b.task_id   = ?
      AND b.run_index = ?
    ORDER BY (c.score_overall - b.score_overall) ASC, b.question_id
    """
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(
            sql, (current, run_index, baseline, run_index)
        ).fetchall()]


def fetch_unpaired(baseline, current, run_index=1):
    """
    找出只在一侧出现的题。

    这个必须有 —— 如果基线 30 题、当前只有 28 题，
    INNER JOIN 会安静地只返回 28 行，看起来对比成功了，
    实际上少的两题被悄悄吞掉。回归报告最忌讳这种「静默丢失」。
    """
    sql = """
    SELECT 'only_baseline' AS side, b.question_id AS qid
    FROM results b
    LEFT JOIN results c
      ON c.question_id = b.question_id
     AND c.task_id     = ?
     AND c.run_index   = ?
    WHERE b.task_id = ? AND b.run_index = ? AND c.id IS NULL

    UNION ALL

    SELECT 'only_current' AS side, c.question_id AS qid
    FROM results c
    LEFT JOIN results b
      ON b.question_id = c.question_id
     AND b.task_id     = ?
     AND b.run_index   = ?
    WHERE c.task_id = ? AND c.run_index = ? AND b.id IS NULL
    """
    with db.get_conn() as conn:
        rows = conn.execute(
            sql, (current, run_index, baseline, run_index,
                  baseline, run_index, current, run_index)
        ).fetchall()
    return {
        "only_baseline": [r[1] for r in rows if r[0] == "only_baseline"],
        "only_current": [r[1] for r in rows if r[0] == "only_current"],
    }


# ============================================================
# 摘要：SQL 版 与 Python 版各算一遍，互相校验
# ============================================================
def summary_by_sql(baseline, current, run_index=1):
    """
    纯 SQL 算摘要。

    单独写一份的目的是「对账」：SQL 版和 Python 版必须给出同一个数，
    不一致就说明有一边的 JOIN 条件或过滤逻辑写错了。
    这类错误肉眼看不出来，只会让报告里的均值偏一点点。
    """
    sql = """
    SELECT
        COUNT(*)                                          AS n,
        ROUND(AVG(b.score_overall), 4)                    AS b_mean,
        ROUND(AVG(c.score_overall), 4)                    AS c_mean,
        ROUND(AVG(c.score_overall - b.score_overall), 4)  AS mean_diff,
        SUM(CASE WHEN c.score_overall < b.score_overall THEN 1 ELSE 0 END) AS regressed,
        SUM(CASE WHEN c.score_overall > b.score_overall THEN 1 ELSE 0 END) AS improved,
        SUM(CASE WHEN c.score_overall = b.score_overall THEN 1 ELSE 0 END) AS same
    FROM results b
    JOIN results c
      ON c.question_id = b.question_id
     AND c.task_id     = ?
     AND c.run_index   = ?
    WHERE b.task_id   = ?
      AND b.run_index = ?
    """
    with db.get_conn() as conn:
        return dict(conn.execute(
            sql, (current, run_index, baseline, run_index)
        ).fetchone())


def summary_by_python(pairs):
    """Python 版摘要，用来和 SQL 版对账"""
    n = len(pairs)
    if not n:
        return {"n": 0, "b_mean": 0.0, "c_mean": 0.0, "mean_diff": 0.0,
                "regressed": 0, "improved": 0, "same": 0}
    b_vals = [p["b_overall"] for p in pairs if p["b_overall"] is not None]
    c_vals = [p["c_overall"] for p in pairs if p["c_overall"] is not None]
    diffs = [p["c_overall"] - p["b_overall"] for p in pairs
             if p["b_overall"] is not None and p["c_overall"] is not None]
    return {
        "n": n,
        "b_mean": round(sum(b_vals) / len(b_vals), 4) if b_vals else 0.0,
        "c_mean": round(sum(c_vals) / len(c_vals), 4) if c_vals else 0.0,
        "mean_diff": round(sum(diffs) / len(diffs), 4) if diffs else 0.0,
        "regressed": sum(1 for d in diffs if d < 0),
        "improved": sum(1 for d in diffs if d > 0),
        "same": sum(1 for d in diffs if d == 0),
    }


def avg(values):
    """求均值，空列表返回 0.0（不抛异常，报表里直接显示 0）"""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


# ============================================================
# 报表
# ============================================================
def report(pairs, baseline, current, top_n=TOP_N):
    if not pairs:
        print("[!] 没有配对成功的题，检查两个 task 是否跑的是同一批题库")
        return

    print("\n" + "=" * 62)
    print(f"回归对比：{baseline}")
    print(f"      →   {current}")
    print("=" * 62)

    # ---------- 一、宏观 ----------
    print("\n一、宏观：五维均分对比")
    print("-" * 62)
    print(f"{'维度':<10}{'基线':>10}{'当前':>10}{'delta':>10}")
    print("-" * 62)

    for field, name in DIMENSIONS:
        bkey = "b_" + field.replace("score_", "")
        ckey = "c_" + field.replace("score_", "")
        b_avg = avg([p[bkey] for p in pairs])
        c_avg = avg([p[ckey] for p in pairs])
        print(f"{name:<10}{b_avg:>10.4f}{c_avg:>10.4f}{c_avg - b_avg:>+10.4f}")

    b_all = avg([p["b_overall"] for p in pairs])
    c_all = avg([p["c_overall"] for p in pairs])
    print("-" * 62)
    print(f"{'总分':<10}{b_all:>10.4f}{c_all:>10.4f}{c_all - b_all:>+10.4f}")
    print("-" * 62)

    # ---------- 二、中观 ----------
    print("\n二、中观：安全题专项")
    print("-" * 62)
    safe = [p for p in pairs if (p["topic"] == "安全") or (p["qtype"] == "safety_trap")]
    print(f"安全题共 {len(safe)} 道")
    if safe:
        for field, name in DIMENSIONS:
            if name != "安全性":
                continue
            bkey = "b_" + field.replace("score_", "")
            ckey = "c_" + field.replace("score_", "")
            print(f"  {name}均分    基线 {avg([p[bkey] for p in safe]):.4f}"
                  f"  当前 {avg([p[ckey] for p in safe]):.4f}")
        veto_b = sum(1 for p in safe if p["b_vetoed"])
        veto_c = sum(1 for p in safe if p["c_vetoed"])
        print(f"  触发安全否决  基线 {veto_b} 次  当前 {veto_c} 次")
        sb = avg([p["b_overall"] for p in safe])
        sc = avg([p["c_overall"] for p in safe])
        print(f"  总分均分      基线 {sb:.4f}  当前 {sc:.4f}  delta {sc - sb:+.4f}")

    # ---------- 三、微观 ----------
    print(f"\n三、微观：退步最多 TOP{top_n}")
    print("-" * 62)
    worst = sorted(
        [p for p in pairs if p["b_overall"] is not None and p["c_overall"] is not None],
        key=lambda p: p["c_overall"] - p["b_overall"],
    )[:top_n]
    for p in worst:
        d = p["c_overall"] - p["b_overall"]
        print(f"\n  {p['question_id']}（{p['topic']}）  {p['b_overall']:.2f} → "
              f"{p['c_overall']:.2f}  delta {d:+.2f}")
        print(f"    题：{(p['question'] or '')[:60]}")
        if p.get("c_review"):
            print(f"    评语：{p['c_review'][:90]}")

    # ---------- 四、分布 ----------
    print("\n四、分布：进步 / 持平 / 退步")
    print("-" * 62)
    diffs = [p["c_overall"] - p["b_overall"] for p in pairs
             if p["b_overall"] is not None and p["c_overall"] is not None]
    n = len(diffs)
    up = sum(1 for d in diffs if d > 0)
    flat = sum(1 for d in diffs if d == 0)
    down = sum(1 for d in diffs if d < 0)
    if n:
        print(f"  进步 {up} 题（{up / n:.1%}）  持平 {flat} 题（{flat / n:.1%}）  "
              f"退步 {down} 题（{down / n:.1%}）")
    print()


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="两个 task 的逐题回归对比（SQL 自连接版）")
    ap.add_argument("-b", "--baseline", help="基线 task_id")
    ap.add_argument("-c", "--current", help="当前 task_id")
    ap.add_argument("--list", action="store_true", help="列出所有 task")
    ap.add_argument("--top", type=int, default=TOP_N, help="退步榜条数")
    ap.add_argument("--run-index", type=int, default=1, help="对比第几次运行，默认 1")
    ap.add_argument("--no-check", action="store_true", help="跳过可对比性检查")
    args = ap.parse_args()

    if args.list:
        list_tasks()
        return

    if not args.baseline or not args.current:
        ap.print_help()
        print("\n提示：先跑 --list 看有哪些 task 可以配对")
        sys.exit(1)

    if not args.no_check:
        check_comparable(args.baseline, args.current)

    pairs = fetch_pairs(args.baseline, args.current, args.run_index)
    unpaired = fetch_unpaired(args.baseline, args.current, args.run_index)

    print(f"[i] 配对成功 {len(pairs)} 题")
    if unpaired["only_baseline"]:
        print(f"[!] 只在基线里出现的题 {len(unpaired['only_baseline'])} 道："
              f"{unpaired['only_baseline'][:10]}")
    if unpaired["only_current"]:
        print(f"[!] 只在当前里出现的题 {len(unpaired['only_current'])} 道："
              f"{unpaired['only_current'][:10]}")

    report(pairs, args.baseline, args.current, args.top)

    # ---------- 对账：SQL 摘要 vs Python 摘要 ----------
    s_sql = summary_by_sql(args.baseline, args.current, args.run_index)
    s_py = summary_by_python(pairs)
    print("=" * 62)
    print("对账：SQL 摘要 vs Python 摘要")
    print("-" * 62)
    keys = [("n", "题数", 0), ("b_mean", "基线均分", 4), ("c_mean", "当前均分", 4),
            ("mean_diff", "均差", 4), ("regressed", "退步", 0),
            ("improved", "进步", 0), ("same", "持平", 0)]
    mismatch = []
    for k, name, nd in keys:
        a, b = s_sql.get(k), s_py.get(k)
        if nd:
            same = abs((a or 0) - (b or 0)) < 1e-6
            print(f"  {name:<8} SQL {a:>10.{nd}f}   Python {b:>10.{nd}f}   "
                  f"{'一致' if same else '不一致'}")
        else:
            same = (a or 0) == (b or 0)
            print(f"  {name:<8} SQL {a:>10}   Python {b:>10}   "
                  f"{'一致' if same else '不一致'}")
        if not same:
            mismatch.append(name)
    print("=" * 62)
    if mismatch:
        print(f"[!] 有 {len(mismatch)} 项对不上：{mismatch}，检查 JOIN 条件")
        sys.exit(2)
    print("[ok] 两套算法结果完全一致，SQL 可信")


if __name__ == "__main__":
    main()
