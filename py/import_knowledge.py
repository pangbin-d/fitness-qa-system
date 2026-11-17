# -*- coding: utf-8 -*-
"""
把 data/knowledge_base.json（100 条权威机构知识）导入 knowledge 表。

这一步只做「原文入库」，不做向量化。向量化是 embed_knowledge.py 的事，
分开的原因：原文入库是确定性操作（失败可重跑），embedding 要花钱/花时间，
两者混在一起出错后不好定位。

用法：
    python3 py/import_knowledge.py --check    # 只体检，不写库
    python3 py/import_knowledge.py            # 正式导入
    python3 py/import_knowledge.py --force    # 已有记录也覆盖

体检项：
    1. 必填字段是否齐全（config.KB.required_fields）
    2. topic 是否在标准六类内
    3. content 长度是否在 [KB.content_min, KB.content_max]
    4. id 是否唯一
    5. content 是否重复（重复条目会让 RAG 检索重复命中）
    6. source.title / source.page 是否非空
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import init_db as db
from config import DATA_VERSION, KB

BASE_DIR = Path(__file__).parent.parent
KB_PATH = BASE_DIR / "data" / "knowledge_base.json"


def load_raw():
    if not KB_PATH.exists():
        raise SystemExit(f"❌ 找不到知识库文件：{KB_PATH}")
    data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"❌ 顶层结构应为 list，实际是 {type(data).__name__}")
    return data


def validate(items):
    """返回 (errors, warnings)。errors 非空时禁止写库。"""
    errors, warnings = [], []
    seen_ids, seen_content = {}, {}

    for idx, it in enumerate(items, 1):
        tag = f"第 {idx} 条"

        # 1. 必填字段
        for f in KB["required_fields"]:
            if f not in it or it[f] in (None, ""):
                errors.append(f"{tag} 缺字段 {f}")
        if errors and errors[-1].startswith(tag):
            continue

        kid = str(it["id"]).strip()
        tag = f"{tag}（{kid}）"

        # 2. topic 合法性
        if it["topic"] not in KB["topics"]:
            errors.append(f"{tag} topic「{it['topic']}」不在标准六类 {KB['topics']} 内")

        # 3. content 长度
        n = len(str(it["content"]).strip())
        if n < KB["content_min"]:
            warnings.append(f"{tag} content 仅 {n} 字，偏短（下限 {KB['content_min']}）")
        elif n > KB["content_max"]:
            warnings.append(f"{tag} content {n} 字，超上限 {KB['content_max']}，建议拆分")

        # 4. id 唯一
        if kid in seen_ids:
            errors.append(f"{tag} id 与第 {seen_ids[kid]} 条重复")
        seen_ids[kid] = idx

        # 5. content 重复
        c = str(it["content"]).strip()
        if c in seen_content:
            errors.append(f"{tag} content 与第 {seen_content[c]} 条完全重复")
        seen_content[c] = idx

        # 6. source 子字段
        src = it.get("source") or {}
        if not isinstance(src, dict):
            errors.append(f"{tag} source 应为对象，实际是 {type(src).__name__}")
        else:
            for f in KB["source_required_fields"]:
                if not src.get(f):
                    errors.append(f"{tag} source.{f} 为空")

    return errors, warnings


def import_items(items, force=False):
    added = updated = skipped = 0
    existing = {k["id"] for k in db.list_knowledge(limit=0)}

    for it in items:
        kid = str(it["id"]).strip()
        src = it.get("source") or {}
        if kid in existing and not force:
            skipped += 1
            continue
        db.upsert_knowledge(
            kid=kid,
            topic=it["topic"],
            content=str(it["content"]).strip(),
            aspect=it.get("aspect"),
            source_title=src.get("title"),
            source_page=str(src.get("page")) if src.get("page") is not None else None,
            source_note=src.get("note"),
            status="active",
            data_version=DATA_VERSION["kb"],
        )
        if kid in existing:
            updated += 1
        else:
            added += 1
    return added, updated, skipped


def report(items):
    print(f"文件：{KB_PATH}")
    print(f"条数：{len(items)}\n")
    print("topic 分布：")
    for k, v in Counter(it.get("topic") for it in items).most_common():
        flag = "" if k in KB["topics"] else "  ⚠️ 不在标准六类"
        print(f"  {k:<10} {v:>3}{flag}")
    lens = [len(str(it.get('content', '')).strip()) for it in items]
    print(f"\ncontent 长度：最短 {min(lens)}，最长 {max(lens)}，平均 {sum(lens)//len(lens)}")
    print(f"aspect 种类：{len({it.get('aspect') for it in items})} 个")
    srcs = Counter((it.get('source') or {}).get('title') for it in items)
    print("\n来源分布：")
    for k, v in srcs.most_common():
        print(f"  {k:<34} {v:>3}")


def main():
    ap = argparse.ArgumentParser(description="导入知识库到 knowledge 表")
    ap.add_argument("--check", action="store_true", help="只体检，不写库")
    ap.add_argument("--force", action="store_true", help="已有记录也覆盖")
    args = ap.parse_args()

    items = load_raw()
    report(items)

    print("\n" + "=" * 60)
    errors, warnings = validate(items)
    if warnings:
        print(f"\n⚠️ 警告 {len(warnings)} 条：")
        for w in warnings:
            print("   ", w)
    if errors:
        print(f"\n❌ 错误 {len(errors)} 条（禁止写库）：")
        for e in errors:
            print("   ", e)
        raise SystemExit(1)
    print("✅ 体检通过，无错误")

    if args.check:
        print("\n（--check 模式，未写库）")
        return

    print("\n" + "=" * 60)
    added, updated, skipped = import_items(items, force=args.force)
    print(f"新增 {added} 条 | 更新 {updated} 条 | 跳过（已存在）{skipped} 条")

    st = db.knowledge_stats()
    print(f"\n=== knowledge 表现状 ===")
    print(f"  总条数：{st.get('total', 0)}")
    for k, v in sorted((st.get("by_topic") or {}).items()):
        print(f"    {k:<10} {v}")


if __name__ == "__main__":
    main()
